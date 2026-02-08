/**
 * SequentialThinkingGraph - Complex Multi-Node LangGraph Flow
 *
 * A graph implementation that handles iterative problem-solving
 * with confidence evaluation, checkpointing, and reflexion.
 * Uses tag-based routing for model selection:
 * - Worker: agent role tags (e.g., tier2 + tools + programming)
 * - Reflection: one tier above worker + thinking
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, getTools } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType, type AgentRole, type ExecutionTurn, type ToolCall } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import { setupSession } from '../../../pipeline/session';
import { calculateConfidence, getConfidenceLevel } from '../confidence';
import { acquireLock as acquireRedisLock, checkAbortFlag } from '../../redis';
import { streamProgressToDiscord } from '../../agentic/progress';
import { loadPrompt } from '../../../templates/loader';
import { getTemplateForAgent } from '../../../templates/registry';
import { getReflectionTags } from '../model-tiers';
import type { GraphResult, GraphInvokeOptions } from './types';
import type { Message, EscalationEvent, LogEntry } from '../state';

const log = createLogger('GRAPH:SEQUENTIAL');

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_TURNS = 20;
const CHECKPOINT_INTERVAL = 5;

// ============================================================================
// State Types
// ============================================================================

export interface SequentialGraphState {
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  agentRole?: string;
  workspacePath: string;
  turnNumber: number;
  maxTurns: number;
  currentTags: string[];
  conversationHistory: Message[];
  turns: ExecutionTurn[];
  confidenceScore: number;
  consecutiveLowConfidenceTurns: number;
  errorCount: number;
  sameErrorCount: number;
  lastError: string | null;
  noProgressTurns: number;
  fileChanges: string[];
  escalations: EscalationEvent[];
  status: 'running' | 'complete' | 'error' | 'stuck' | 'needs_clarification' | 'aborted';
  abortRequested: boolean;
  totalInputTokens: number;
  totalOutputTokens: number;
  finalResponse: string;
  traversedNodes: string[];
  logBuffer: LogEntry[];
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
  const agentRole = options.agentRole as AgentRole || 'python-coder';
  const tags = options.tags || ['tier2', 'tools', 'programming'];

  return {
    channelId: options.channelId,
    executionId: options.executionId,
    initialPrompt: options.initialPrompt,
    flowType: FlowType.SEQUENTIAL_THINKING,
    agentRole,
    workspacePath: options.workspacePath || options.channelId,
    turnNumber: 0,
    maxTurns: DEFAULT_MAX_TURNS,
    currentTags: tags,
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
  };
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

function parseTurn(response: unknown, turnNumber: number): Partial<ExecutionTurn> {
  const choice = (response as any)?.choices?.[0];
  const message = choice?.message;

  const toolCalls: ToolCall[] = message?.tool_calls || [];
  const content = message?.content || '';

  let confidence = 70;
  const confidenceMatch = content.match(/confidence[:\s]+(\d+)/i);
  if (confidenceMatch) {
    confidence = parseInt(confidenceMatch[1], 10);
  }

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
    toolResults: [],
    response: content,
    confidence,
    status,
    modelUsed: `auto`,
  };
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createSequentialGraph() {
  return {
    name: 'SequentialThinkingGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking SequentialThinkingGraph for channel ${options.channelId}`);
      log.info(`Using tags: ${(options.tags || ['tier2', 'tools', 'programming']).join(', ')}`);

      const state = createInitialState(options);
      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      logger.recordNode('start');

      try {
        // Setup: acquire lock, create session
        logger.recordNode('setup');
        
        const abortFlag = await checkAbortFlag(state.channelId);
        if (abortFlag) {
          log.warn('Abort flag detected');
          return {
            response: 'Task aborted',
            model: `auto:${state.currentTags.join(',')}`,
            traversedNodes: ['start', 'setup'],
          };
        }

        const lockAcquired = await acquireRedisLock(state.channelId, state.executionId);
        if (!lockAcquired) {
          log.error('Failed to acquire lock');
          return {
            response: 'Could not acquire lock',
            model: `auto:${state.currentTags.join(',')}`,
            traversedNodes: ['start', 'setup'],
            error: 'Lock acquisition failed',
          };
        }

        const sessionResult = await setupSession(state.workspacePath, state.channelId);
        log.info(`Session created: ${sessionResult.branchName}`);

        // Initialize conversation
        const systemPrompt = await getSystemPrompt(
          (state.agentRole as AgentRole) || 'python-coder',
          state.workspacePath
        );
        
        const conversationHistory: Message[] = [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: state.initialPrompt },
        ];

        logger.recordNode('execute_turn_1');

        // Execute turn
        const params = getModelParams(FlowType.SEQUENTIAL_THINKING);
        
        const response = await chatCompletion({
          model: 'auto',
          messages: conversationHistory,
          temperature: params.temperature,
          top_p: params.top_p,
          metadata: {
            tags: state.currentTags,
          },
        });

        const turnData = parseTurn(response, 1);
        const modelUsed = response.model;
        log.info(`Turn 1 executed, confidence: ${turnData.confidence}`);

        // Stream progress
        await streamProgressToDiscord(state.channelId, {
          type: 'turn_start',
          turnNumber: 1,
          maxTurns: state.maxTurns,
          model: modelUsed,
          confidence: turnData.confidence,
        });

        // Evaluate
        logger.recordNode('evaluate');
        
        const confidence = calculateConfidence({} as any, turnData as ExecutionTurn);
        const confidenceLevel = getConfidenceLevel(confidence);
        log.info(`Confidence: ${confidence}% (${confidenceLevel})`);

        // Generate final response
        const finalResponse = turnData.response || 'Task completed';

        logger.recordNode('finalize');

        // Generate Mermaid diagram
        const generator = getMermaidGenerator();
        const mermaidSource = generator.generate({
          flowType: FlowType.SEQUENTIAL_THINKING,
          traversedNodes: ['start', 'setup', 'execute_turn_1', 'evaluate', 'finalize'],
          turns: [turnData as ExecutionTurn],
          finalStatus: 'complete',
        });

        await logger.uploadMermaid(mermaidSource);
        const mermaidPng = await generator.renderPng(mermaidSource);
        await logger.uploadDiagramPng(mermaidPng);

        // Upload metadata
        const metadata = {
          flowType: FlowType.SEQUENTIAL_THINKING,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'complete',
          nodeCount: 5,
          model: modelUsed,
          tags: state.currentTags,
          turns: 1,
          confidence,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        log.info(`Sequential thinking complete, status: complete`);

        return {
          response: finalResponse,
          model: modelUsed,
          traversedNodes: ['start', 'setup', 'execute_turn_1', 'evaluate', 'finalize'],
        };

      } catch (error) {
        log.error(`Sequential thinking error: ${error}`);

        const metadata = {
          flowType: FlowType.SEQUENTIAL_THINKING,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'error',
          error: String(error),
          tags: state.currentTags,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        return {
          response: `Error: ${error instanceof Error ? error.message : String(error)}`,
          model: `auto:${state.currentTags.join(',')}`,
          traversedNodes: ['start', 'setup', 'error'],
          error: String(error),
        };
      }
    },
  };
}

// Export singleton
export const sequentialGraph = createSequentialGraph();
