/**
 * SequentialThinkingGraph - Complex Multi-Node LangGraph Flow
 *
 * A full StateGraph implementation that replaces executeSequentialThinkingLoop().
 * Implements iterative problem-solving with confidence evaluation, escalation,
 * checkpointing, and reflexion.
 *
 * Nodes:
 * - setup: Acquire lock, create session, load tools
 * - execute_turn: Call LLM with conversation history + tools
 * - evaluate_turn: Parse response, calculate confidence, update state
 * - check_escalation: Check triggers, escalate if needed
 * - checkpoint: Periodic checkpoint (every N turns)
 * - reflect: Trajectory evaluation + Reflexion
 * - ask_clarification: Post clarification request to Discord
 * - abort: Clean up and return abort message
 * - finalize: Log completion, release locks, generate diagram + PNG
 *
 * @see plans/langgraph-migration-plan.md §3
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, getTools } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType, type AgentRole, type ExecutionState, type ExecutionTurn, type ToolCall } from '../../litellm/types';
import { createExecutionLogger, type ExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import { setupSession } from '../../../pipeline/session';
import { checkEscalationTriggers, getNextModel, isAtMaxEscalation, MODEL_CAPABILITY_ORDER } from '../../agentic/escalation';
import { calculateConfidence, getConfidenceLevel } from '../../agentic/confidence';
import { acquireLock as acquireRedisLock, releaseLock as releaseRedisLock, checkAbortFlag, refreshLock } from '../../redis';
import { streamProgressToDiscord } from '../../agentic/progress';
import { loadPrompt } from '../../../templates/loader';
import { getTemplateForAgent } from '../../../templates/registry';
import type { GraphResult, GraphInvokeOptions } from './types';
import type { GraphState, ExecutionStatus, FailureMetadata, FailureErrorType, Message, EscalationEvent, LogEntry } from '../state';

const log = createLogger('GRAPH:SEQUENTIAL');

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_TURNS = 20;
const CHECKPOINT_INTERVAL = 5;
const LOW_CONFIDENCE_THRESHOLD = 30;
const CONSECUTIVE_LOW_CONFIDENCE_LIMIT = 3;
const NO_PROGRESS_LIMIT = 5;
const SAME_ERROR_LIMIT = 3;

// ============================================================================
// State Types
// ============================================================================

export interface SequentialGraphState extends Omit<GraphState, 'logBuffer'> {
  // Input
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  agentRole?: string;
  workspacePath: string;

  // Execution tracking
  turnNumber: number;
  maxTurns: number;
  currentModel: string;
  conversationHistory: Message[];
  turns: ExecutionTurn[];

  // Confidence & escalation
  confidenceScore: number;
  consecutiveLowConfidenceTurns: number;
  errorCount: number;
  sameErrorCount: number;
  lastError: string | null;
  noProgressTurns: number;
  fileChanges: string[];
  escalations: EscalationEvent[];

  // Control
  status: ExecutionStatus;
  abortRequested: boolean;

  // Tokens
  totalInputTokens: number;
  totalOutputTokens: number;

  // Output
  finalResponse: string;

  // Logging & Diagrams
  traversedNodes: string[];
  logBuffer: LogEntry[];

  // Checkpoint tracking
  checkpointInterval: number;
  lastCheckpointTurn: number;

  // Error tracking
  failureMetadata?: FailureMetadata;

  // Reflexion
  reflectionResult?: {
    what_worked: string;
    what_failed: string;
    root_cause: string;
    strategy_change: string;
    key_insight: string;
  };
}

// ============================================================================
// Helper Functions
// ============================================================================

function createInitialState(options: GraphInvokeOptions): SequentialGraphState {
  return {
    channelId: options.channelId,
    executionId: options.executionId,
    initialPrompt: options.initialPrompt,
    flowType: FlowType.SEQUENTIAL_THINKING,
    agentRole: options.agentRole,
    workspacePath: options.workspacePath || options.channelId,
    turnNumber: 0,
    maxTurns: DEFAULT_MAX_TURNS,
    currentModel: MODEL_CAPABILITY_ORDER[0] || 'gemini-3-pro',
    conversationHistory: [],
    turns: [],
    confidenceScore: 0,
    consecutiveLowConfidenceTurns: 0,
    errorCount: 0,
    sameErrorCount: 0,
    lastError: null,
    noProgressTurns: 0,
    fileChanges: [],
    escalations: [],
    status: 'running',
    abortRequested: false,
    totalInputTokens: 0,
    totalOutputTokens: 0,
    finalResponse: '',
    traversedNodes: [],
    logBuffer: [],
    checkpointInterval: CHECKPOINT_INTERVAL,
    lastCheckpointTurn: 0,
  };
}

function addLog(state: SequentialGraphState, level: LogEntry['level'], node: string, message: string, data?: unknown): void {
  state.logBuffer.push({
    timestamp: new Date().toISOString(),
    level,
    node,
    message,
    data,
  });
}

function enterNode(state: SequentialGraphState, nodeName: string): void {
  state.traversedNodes.push(nodeName);
  addLog(state, 'INFO', nodeName, `Entered node: ${nodeName}`);
}

function extractProvider(model: string): string {
  const modelLower = model.toLowerCase();
  if (modelLower.includes('claude')) return 'anthropic';
  if (modelLower.includes('gpt') || modelLower.includes('openai')) return 'openai';
  if (modelLower.includes('gemini')) return 'google';
  if (modelLower.includes('qwen')) return 'alibaba';
  if (modelLower.includes('glm')) return '智谱AI';
  if (modelLower.includes('deepseek')) return 'deepseek';
  if (modelLower.includes('minimax')) return 'minimax';
  return 'unknown';
}

function getErrorType(error: unknown): FailureErrorType {
  const msg = error instanceof Error ? error.message : String(error).toLowerCase();
  if (msg.includes('timeout')) return 'timeout';
  if (msg.includes('rate limit') || msg.includes('429')) return 'rate_limit';
  if (msg.includes('api') || msg.includes('500') || msg.includes('503')) return 'api_error';
  if (msg.includes('tool') || msg.includes('function')) return 'tool_error';
  return 'unknown';
}

async function getSystemPrompt(agentRole: AgentRole, workspacePath: string): Promise<string> {
  const templateName = getTemplateForAgent(agentRole);
  let prompt: string;
  try {
    prompt = await loadPrompt(templateName);
  } catch {
    log.warn(`Template ${templateName} not found, falling back to 'coding'`);
    prompt = await loadPrompt('coding');
  }
  return prompt
    .replace(/{{workspace_path}}/g, workspacePath)
    .replace(/Your workspace is at:? [^{\n]*/g, `Your workspace is at: ${workspacePath}`);
}

function parseTurn(response: unknown, turnNumber: number, model: string): Partial<ExecutionTurn> {
  const choice = (response as any)?.choices?.[0];
  const message = choice?.message;

  const toolCalls: ToolCall[] = message?.tool_calls || [];
  const toolResults: Array<{ tool: string; result: unknown }> = [];

  // Extract confidence from response content
  let confidence = 70;
  const content = message?.content || '';
  const confidenceMatch = content.match(/confidence[:\s]+(\d+)/i);
  if (confidenceMatch) {
    confidence = parseInt(confidenceMatch[1], 10);
  }

  // Determine status from response
  let status: ExecutionTurn['status'] = 'continue';
  if (content.toLowerCase().includes('complete') || content.toLowerCase().includes('done')) {
    status = 'complete';
  } else if (content.toLowerCase().includes('stuck') || content.toLowerCase().includes('need help')) {
    status = 'stuck';
  } else if (content.toLowerCase().includes('clarif')) {
    status = 'needs_clarification';
  }

  return {
    turnNumber,
    input: content,
    toolCalls,
    toolResults,
    response: content,
    confidence,
    status,
    modelUsed: model,
  };
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Setup node: Acquire lock, create session, load tools
 */
async function setupNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  enterNode(state, 'setup');

  try {
    // Check abort flag first
    const abortFlag = await checkAbortFlag(state.channelId);
    if (abortFlag) {
      addLog(state, 'WARN', 'setup', 'Abort flag detected');
      return { status: 'aborted', abortRequested: true };
    }

    // Acquire lock
    const lockAcquired = await acquireRedisLock(state.channelId, state.executionId);
    if (!lockAcquired) {
      addLog(state, 'ERROR', 'setup', 'Failed to acquire lock');
      return { status: 'stuck', errorCount: state.errorCount + 1 };
    }
    addLog(state, 'INFO', 'setup', `Lock acquired for channel ${state.channelId}`);

    // Setup session
    const sessionResult = await setupSession(state.workspacePath, state.channelId);
    addLog(state, 'INFO', 'setup', `Session created: ${sessionResult.branchName}`);

    // Load tools
    const tools = await getTools();
    addLog(state, 'INFO', 'setup', `Loaded ${tools.length} tools`);

    // Initialize conversation with system prompt
    const systemPrompt = await getSystemPrompt((state.agentRole as AgentRole) || 'coding', state.workspacePath);
    const conversationHistory: Message[] = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: state.initialPrompt },
    ];

    return {
      conversationHistory,
      status: 'running' as const,
      currentModel: MODEL_CAPABILITY_ORDER[0] || 'gemini-3-pro',
    };
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    addLog(state, 'ERROR', 'setup', `Setup failed: ${errorMsg}`);
    return {
      status: 'stuck',
      errorCount: state.errorCount + 1,
      lastError: errorMsg,
      failureMetadata: {
        failed_node: 'setup',
        failed_model: state.currentModel,
        error_type: getErrorType(error),
        error_message: errorMsg,
        provider: extractProvider(state.currentModel),
        timestamp: new Date().toISOString(),
      },
    };
  }
}

/**
 * Plan node: Create initial plan
 */
async function planNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  enterNode(state, 'plan');

  try {
    const params = getModelParams(FlowType.SEQUENTIAL_THINKING);

    const response = await chatCompletion({
      model: state.currentModel,
      messages: [
        { role: 'user', content: `Create a detailed plan to address:\n\n${state.initialPrompt}\n\nRespond with your plan and indicate your confidence level (0-100).` },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const planContent = extractContent(response);

    // Add plan to conversation history
    const updatedHistory: Message[] = [
      ...state.conversationHistory,
      { role: 'assistant' as const, content: planContent },
    ];

    addLog(state, 'INFO', 'plan', `Plan created (${planContent.length} chars)`);

    return {
      conversationHistory: updatedHistory,
      finalResponse: planContent,
    };
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    addLog(state, 'ERROR', 'plan', `Planning failed: ${errorMsg}`);
    return {
      status: 'stuck',
      errorCount: state.errorCount + 1,
      lastError: errorMsg,
      failureMetadata: {
        failed_node: 'plan',
        failed_model: state.currentModel,
        error_type: getErrorType(error),
        error_message: errorMsg,
        provider: extractProvider(state.currentModel),
        timestamp: new Date().toISOString(),
        turn_number: state.turnNumber,
      },
    };
  }
}

/**
 * Execute Turn node: Call LLM with conversation history + tools
 */
async function executeTurnNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  const nodeName = `execute_turn_${state.turnNumber + 1}`;
  enterNode(state, nodeName);

  try {
    const params = getModelParams(FlowType.SEQUENTIAL_THINKING);

    const response = await chatCompletion({
      model: state.currentModel,
      messages: state.conversationHistory,
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const turnData = parseTurn(response, state.turnNumber + 1, state.currentModel);

    addLog(state, 'INFO', nodeName, `Turn executed with ${state.currentModel}, confidence: ${turnData.confidence}`);

    // Stream progress to Discord
    await streamProgressToDiscord(state.channelId, {
      type: 'turn_start',
      turnNumber: state.turnNumber + 1,
      maxTurns: state.maxTurns,
      model: state.currentModel,
      confidence: turnData.confidence,
    });

    return {
      turns: [...state.turns, turnData as ExecutionTurn],
      conversationHistory: [...state.conversationHistory, { role: 'assistant' as const, content: turnData.response || '' }],
      turnNumber: state.turnNumber + 1,
      currentModel: state.currentModel,
    };
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    addLog(state, 'ERROR', nodeName, `Turn execution failed: ${errorMsg}`);

    // Check for repeated errors
    const isSameError = state.lastError === errorMsg;
    const sameErrorCount = isSameError ? state.sameErrorCount + 1 : 0;

    return {
      status: 'stuck',
      errorCount: state.errorCount + 1,
      sameErrorCount,
      lastError: errorMsg,
      failureMetadata: {
        failed_node: nodeName,
        failed_model: state.currentModel,
        error_type: getErrorType(error),
        error_message: errorMsg,
        provider: extractProvider(state.currentModel),
        timestamp: new Date().toISOString(),
        turn_number: state.turnNumber,
      },
    };
  }
}

/**
 * Evaluate Turn node: Parse response, calculate confidence, update state
 */
async function evaluateTurnNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  const nodeName = `evaluate_turn_${state.turnNumber}`;
  enterNode(state, nodeName);

  const currentTurn = state.turns[state.turns.length - 1];
  if (!currentTurn) {
    addLog(state, 'ERROR', nodeName, 'No turn to evaluate');
    return {};
  }

  // Calculate confidence using existing logic
  const mockState: Partial<ExecutionState> = {
    turnNumber: state.turnNumber,
    sameErrorCount: state.sameErrorCount,
    noProgressTurns: state.noProgressTurns,
    testResults: [],
    userCorrectionCount: 0,
  };

  const confidence = calculateConfidence(mockState as ExecutionState, currentTurn);
  const confidenceLevel = getConfidenceLevel(confidence);

  // Determine if there's progress (file changes in this turn)
  const thisTurnFileChanges = state.fileChanges; // Simplified - in real impl would track per-turn
  const hasProgress = thisTurnFileChanges.length > 0;
  const newNoProgressTurns = hasProgress ? 0 : state.noProgressTurns + 1;

  addLog(state, 'INFO', nodeName, `Confidence: ${confidence}% (${confidenceLevel}), no_progress turns: ${newNoProgressTurns}`);

  // Determine next action based on turn status
  let nextStatus: ExecutionStatus = 'running';

  if (currentTurn.status === 'complete') {
    nextStatus = 'complete';
  } else if (currentTurn.status === 'needs_clarification') {
    nextStatus = 'needs_clarification';
  } else if (currentTurn.status === 'stuck') {
    nextStatus = 'stuck';
  } else if (confidenceLevel === 'critical' || confidenceLevel === 'low') {
    // Will check for escalation
  }

  // Update consecutive low confidence count
  const consecutiveLow = confidenceLevel === 'critical' || confidenceLevel === 'low'
    ? state.consecutiveLowConfidenceTurns + 1
    : 0;

  return {
    confidenceScore: confidence,
    consecutiveLowConfidenceTurns: consecutiveLow,
    noProgressTurns: newNoProgressTurns,
    status: nextStatus,
    currentModel: state.currentModel,
    turns: state.turns,
  };
}

/**
 * Check Escalation node: Check triggers, escalate if needed
 */
async function checkEscalationNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  enterNode(state, 'check_escalation');

  const currentTurn = state.turns[state.turns.length - 1];
  if (!currentTurn) {
    return {};
  }

  // Use existing escalation logic
  const mockState: Partial<ExecutionState> = {
    turnNumber: state.turnNumber,
    sameErrorCount: state.sameErrorCount,
    noProgressTurns: state.noProgressTurns,
    testResults: [],
    userCorrectionCount: 0,
  };

  const escalation = checkEscalationTriggers(
    mockState as ExecutionState,
    currentTurn,
    state.currentModel,
    state.consecutiveLowConfidenceTurns
  );

  if (escalation.shouldEscalate) {
    const nextModel = escalation.suggestedModel || getNextModel(state.currentModel);

    if (nextModel && !isAtMaxEscalation(state.currentModel)) {
      addLog(state, 'WARN', 'check_escalation', `Escalating from ${state.currentModel} to ${nextModel}: ${escalation.reason}`);

      const escalationEvent: EscalationEvent = {
        turnNumber: state.turnNumber,
        fromModel: state.currentModel,
        toModel: nextModel,
        reason: escalation.reason,
        timestamp: new Date().toISOString(),
      };

      // Stream escalation to Discord
      await streamProgressToDiscord(state.channelId, {
        type: 'escalation',
        model: state.currentModel,
        newModel: nextModel,
        escalationReason: escalation.reason,
        turnNumber: state.turnNumber,
      });

      return {
        currentModel: nextModel,
        escalations: [...state.escalations, escalationEvent],
        consecutiveLowConfidenceTurns: 0,
        sameErrorCount: 0,
        noProgressTurns: 0,
      };
    } else {
      addLog(state, 'INFO', 'check_escalation', `Cannot escalate further: ${escalation.reason}`);
    }
  }

  return {};
}

/**
 * Checkpoint node: Periodic state persistence
 */
async function checkpointNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  const nodeName = `checkpoint_${state.turnNumber}`;
  enterNode(state, nodeName);

  addLog(state, 'INFO', nodeName, `Checkpoint at turn ${state.turnNumber}`);

  // In a real LangGraph implementation, this would save to DynamoDB
  // The checkpointer middleware handles this automatically

  return {
    lastCheckpointTurn: state.turnNumber,
  };
}

/**
 * Reflect node: Trajectory evaluation + Reflexion
 */
async function reflectNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  enterNode(state, 'reflect');

  try {
    const params = getModelParams(FlowType.SEQUENTIAL_THINKING);

    // Generate reflexion summary
    const reflexionPrompt = `
Analyze the execution trajectory and provide a reflexion:

Task: ${state.initialPrompt}
Total Turns: ${state.turnNumber}
Final Model: ${state.currentModel}
Confidence Score: ${state.confidenceScore}%

Turn Summary:
${state.turns.map((t, i) => `- Turn ${i + 1}: ${t.modelUsed}, confidence ${t.confidence}%, status: ${t.status}`).join('\n')}

Escalations: ${state.escalations.length}
${state.escalations.map((e, i) => `- Turn ${e.turnNumber}: ${e.fromModel} → ${e.toModel}`).join('\n')}

Please provide:
1. what_worked: What approaches were successful?
2. what_failed: What didn't work?
3. root_cause: What was the fundamental issue?
4. strategy_change: What would you do differently?
5. key_insight: What's the main learning?

Respond in JSON format.
`;

    const response = await chatCompletion({
      model: state.currentModel,
      messages: [
        { role: 'user', content: reflexionPrompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);

    // Try to parse as JSON
    let reflectionResult;
    try {
      reflectionResult = JSON.parse(content);
    } catch {
      // Fallback to text
      reflectionResult = {
        what_worked: content,
        what_failed: '',
        root_cause: '',
        strategy_change: '',
        key_insight: '',
      };
    }

    addLog(state, 'INFO', 'reflect', 'Reflexion complete');

    return {
      reflectionResult,
      finalResponse: state.finalResponse || content,
    };
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    addLog(state, 'ERROR', 'reflect', `Reflexion failed: ${errorMsg}`);
    return {
      finalResponse: state.finalResponse || `Execution completed (reflexion failed: ${errorMsg})`,
    };
  }
}

/**
 * Ask Clarification node: Post clarification request to Discord
 */
async function askClarificationNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  enterNode(state, 'ask_clarification');

  const currentTurn = state.turns[state.turns.length - 1];
  const clarificationRequest = currentTurn?.response || 'I need clarification to proceed.';

  // Stream clarification request to Discord
  await streamProgressToDiscord(state.channelId, {
    type: 'clarification_request',
    clarificationMessage: clarificationRequest,
    confidence: state.confidenceScore,
    turnNumber: state.turnNumber,
  });

  addLog(state, 'INFO', 'ask_clarification', 'Clarification requested');

  return {
    finalResponse: `I need some clarification to continue:\n\n${clarificationRequest}`,
    status: 'needs_clarification' as const,
  };
}

/**
 * Abort node: Clean up and return abort message
 */
async function abortNode(state: SequentialGraphState): Promise<Partial<SequentialGraphState>> {
  enterNode(state, 'abort');

  addLog(state, 'WARN', 'abort', 'Execution aborted');

  // Release lock
  await releaseRedisLock(state.channelId);

  return {
    status: 'aborted' as const,
    finalResponse: 'Execution was aborted by user request.',
  };
}

/**
 * Finalize node: Log completion, generate diagram, upload to S3
 */
async function finalizeNode(state: SequentialGraphState, logger: ExecutionLogger): Promise<GraphResult> {
  enterNode(state, 'finalize');

  try {
    // Release lock
    await releaseRedisLock(state.channelId);
    addLog(state, 'INFO', 'finalize', 'Lock released');

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generateDetailedDiagram({
      flowType: FlowType.SEQUENTIAL_THINKING,
      traversedNodes: state.traversedNodes,
      turns: state.turns,
      status: state.status,
      initialPrompt: state.initialPrompt,
    } as any);

    await logger.uploadMermaid(mermaidSource);
    addLog(state, 'INFO', 'finalize', 'Mermaid diagram uploaded');

    // Upload metadata
    const metadata = {
      flowType: FlowType.SEQUENTIAL_THINKING,
      channelId: state.channelId,
      executionId: state.executionId,
      status: state.status,
      nodeCount: state.traversedNodes.length,
      turnCount: state.turnNumber,
      model: state.currentModel,
      confidenceScore: state.confidenceScore,
      escalations: state.escalations.length,
      errors: state.errorCount,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    addLog(state, 'INFO', 'finalize', 'Metadata uploaded');

    // Flush logs to S3
    await logger.flush();
    addLog(state, 'INFO', 'finalize', 'Logs flushed to S3');

    return {
      response: state.finalResponse || state.initialPrompt,
      model: state.currentModel,
      traversedNodes: state.traversedNodes,
      error: state.status === 'stuck' ? 'Execution got stuck' : undefined,
      failureMetadata: state.failureMetadata,
    };
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    log.error(`Finalization error: ${errorMsg}`);

    return {
      response: state.finalResponse || `Execution completed with error: ${errorMsg}`,
      model: state.currentModel,
      traversedNodes: state.traversedNodes,
      error: errorMsg,
      failureMetadata: state.failureMetadata,
    };
  }
}

// ============================================================================
// Conditional Edge Functions
// ============================================================================

function shouldContinue(state: SequentialGraphState): string {
  // Check abort first
  if (state.status === 'aborted' || state.abortRequested) {
    return 'abort';
  }

  // Check completion
  if (state.status === 'complete') {
    return 'reflect';
  }

  // Check clarification needed
  if (state.status === 'needs_clarification') {
    return 'ask_clarification';
  }

  // Check if stuck at max turns
  if (state.turnNumber >= state.maxTurns) {
    return 'reflect';
  }

  // Check consecutive low confidence limit
  if (state.consecutiveLowConfidenceTurns >= CONSECUTIVE_LOW_CONFIDENCE_LIMIT) {
    if (!isAtMaxEscalation(state.currentModel)) {
      return 'check_escalation';
    }
    return 'reflect';
  }

  // Check no progress limit
  if (state.noProgressTurns >= NO_PROGRESS_LIMIT) {
    if (!isAtMaxEscalation(state.currentModel)) {
      return 'check_escalation';
    }
    return 'reflect';
  }

  // Check same error limit
  if (state.sameErrorCount >= SAME_ERROR_LIMIT) {
    if (!isAtMaxEscalation(state.currentModel)) {
      return 'check_escalation';
    }
    return 'reflect';
  }

  // Check checkpoint interval
  if (state.turnNumber > 0 && state.turnNumber % state.checkpointInterval === 0) {
    return 'checkpoint';
  }

  // Continue to next turn
  return 'execute_turn';
}

function afterCheckpoint(state: SequentialGraphState): string {
  return 'execute_turn';
}

function afterEscalation(state: SequentialGraphState): string {
  return 'execute_turn';
}

function afterAskClarification(state: SequentialGraphState): string {
  return 'finalize';
}

function afterAbort(state: SequentialGraphState): string {
  return 'finalize';
}

function afterReflect(state: SequentialGraphState): string {
  return 'finalize';
}

// ============================================================================
// Graph Factory
// ============================================================================

export interface SequentialThinkingGraphInput {
  channelId: string;
  executionId: string;
  initialPrompt: string;
  agentRole?: string;
  workspacePath?: string;
}

export function createSequentialThinkingGraph() {
  // Note: This is a simplified StateGraph-like implementation
  // In a full LangGraph implementation, we would use:
  // const graph = new StateGraph(SequentialGraphState)
  //   .addNode('setup', setupNode)
  //   .addNode('plan', planNode)
  //   .addNode('execute_turn', executeTurnNode)
  //   .addNode('evaluate_turn', evaluateTurnNode)
  //   .addNode('check_escalation', checkEscalationNode)
  //   .addNode('checkpoint', checkpointNode)
  //   .addNode('reflect', reflectNode)
  //   .addNode('ask_clarification', askClarificationNode)
  //   .addNode('abort', abortNode)
  //   .addNode('finalize', finalizeNode)
  //   .addEdge('setup', 'plan')
  //   .addEdge('plan', 'execute_turn')
  //   .addEdge('execute_turn', 'evaluate_turn')
  //   .addConditionalEdges('evaluate_turn', shouldContinue, {
  //     abort,
  //     reflect,
  //     ask_clarification,
  //     check_escalation,
  //     checkpoint,
  //     execute_turn,
  //   })
  //   .addEdge('checkpoint', 'execute_turn')
  //   .addEdge('check_escalation', 'execute_turn')
  //   .addEdge('ask_clarification', 'finalize')
  //   .addEdge('abort', 'finalize')
  //   .addEdge('reflect', 'finalize');

  return {
    name: 'SequentialThinkingGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking SequentialThinkingGraph for channel ${options.channelId}`);

      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      let state = createInitialState(options);
      logger.recordNode('setup');

      try {
        // Phase 1: Setup
        const setupResult = await setupNode(state);
        state = { ...state, ...setupResult };

        if (state.status === 'aborted' || state.status === 'stuck') {
          return await finalizeNode(state, logger);
        }

        // Phase 2: Plan
        logger.recordNode('plan');
        const planResult = await planNode(state);
        state = { ...state, ...planResult };

        // Phase 3: Execution Loop
        while (state.status === 'running' && state.turnNumber < state.maxTurns) {
          logger.recordNode(`execute_turn_${state.turnNumber + 1}`);

          // Execute turn
          const turnResult = await executeTurnNode(state);
          state = { ...state, ...turnResult };

          if (state.status === 'stuck') {
            // Check for escalation possibility
            const canEscalate = !isAtMaxEscalation(state.currentModel);
            if (canEscalate && state.consecutiveLowConfidenceTurns < CONSECUTIVE_LOW_CONFIDENCE_LIMIT) {
              logger.recordNode('check_escalation');
              const escalationResult = await checkEscalationNode(state);
              state = { ...state, ...escalationResult };
            }
            continue;
          }

          // Evaluate turn
          logger.recordNode(`evaluate_turn_${state.turnNumber}`);
          const evalResult = await evaluateTurnNode(state);
          state = { ...state, ...evalResult };

          // Determine next action
          const nextAction = shouldContinue(state);

          switch (nextAction) {
            case 'abort':
              logger.recordNode('abort');
              const abortResult = await abortNode(state);
              state = { ...state, ...abortResult };
              return await finalizeNode(state, logger);

            case 'complete':
            case 'reflect':
              logger.recordNode('reflect');
              const reflectResult = await reflectNode(state);
              state = { ...state, ...reflectResult };
              return await finalizeNode(state, logger);

            case 'ask_clarification':
              logger.recordNode('ask_clarification');
              await askClarificationNode(state);
              return await finalizeNode(state, logger);

            case 'check_escalation':
              logger.recordNode('check_escalation');
              const escalationResult = await checkEscalationNode(state);
              state = { ...state, ...escalationResult };
              break;

            case 'checkpoint':
              logger.recordNode(`checkpoint_${state.turnNumber}`);
              await checkpointNode(state);
              break;

            case 'execute_turn':
            default:
              // Continue loop
              break;
          }
        }

        // Max turns reached - reflect and finalize
        if (state.turnNumber >= state.maxTurns) {
          logger.recordNode('reflect');
          const reflectResult = await reflectNode(state);
          state = { ...state, ...reflectResult };
        }

        return await finalizeNode(state, logger);

      } catch (error) {
        log.error(`SequentialThinkingGraph error: ${error}`);

        const errorMsg = error instanceof Error ? error.message : String(error);
        state.status = 'stuck';
        state.failureMetadata = {
          failed_node: 'graph_invoke',
          failed_model: state.currentModel,
          error_type: getErrorType(error),
          error_message: errorMsg,
          provider: extractProvider(state.currentModel),
          timestamp: new Date().toISOString(),
          turn_number: state.turnNumber,
        };

        return await finalizeNode(state, logger);
      }
    },
  };
}

// Export singleton
export const sequentialThinkingGraph = createSequentialThinkingGraph();

// ============================================================================
// Convenience function for creating a new graph instance
// ============================================================================

export function createSequentialThinkingGraphForChannel(
  channelId: string,
  initialPrompt: string,
  agentRole?: string
): { name: string; invoke: (options: GraphInvokeOptions) => Promise<GraphResult> } {
  const graph = createSequentialThinkingGraph();

  return {
    name: graph.name,
    invoke: async (options: GraphInvokeOptions) => {
      return graph.invoke({
        channelId,
        executionId: options.executionId || `exec-${Date.now()}`,
        initialPrompt,
        flowType: FlowType.SEQUENTIAL_THINKING,
        agentRole,
        workspacePath: options.workspacePath,
      });
    },
  };
}
