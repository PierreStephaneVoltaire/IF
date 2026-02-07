/**
 * LangGraph State Types
 *
 * Shared state interfaces for all LangGraph nodes.
 * These types define the graph state that flows between nodes.
 *
 * @see plans/langgraph-migration-plan.md §3
 */

import { FlowType } from '../litellm/types';

// ---------------------------------------------------------------------------
// Core State Interfaces
// ---------------------------------------------------------------------------

/**
 * Core state shared across all graph nodes.
 */
export interface GraphState {
  // Input
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  agentRole?: string;

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

  // Error tracking
  failureMetadata?: FailureMetadata;
}

/**
 * Execution status for graph control flow.
 */
export type ExecutionStatus =
  | 'running'
  | 'complete'
  | 'stuck'
  | 'aborted'
  | 'needs_clarification';

/**
 * Message format for LLM calls.
 */
export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

/**
 * Individual turn in execution history.
 */
export interface ExecutionTurn {
  turnNumber: number;
  input: string;
  toolCalls: ToolCall[];
  toolResults: Array<{ tool: string; result: unknown }>;
  response: string;
  thinking?: string;
  confidence: number;
  status: 'continue' | 'stuck' | 'complete' | 'needs_clarification';
  modelUsed: string;
  inputTokens?: number;
  outputTokens?: number;
}

/**
 * Tool call format.
 */
export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}

/**
 * Escalation event for tracking model changes.
 */
export interface EscalationEvent {
  turnNumber: number;
  fromModel: string;
  toModel: string;
  reason: string;
  timestamp: string;
}

/**
 * Log entry for per-execution logging.
 */
export interface LogEntry {
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
  node: string;
  message: string;
  data?: unknown;
}

/**
 * Failure metadata for checkpointing.
 */
export interface FailureMetadata {
  failed_node: string;
  failed_model: string;
  error_type: FailureErrorType;
  error_message: string;
  provider: string;
  timestamp: string;
  turn_number?: number;
}

/**
 * Types of failures that can occur.
 */
export type FailureErrorType =
  | 'timeout'
  | 'rate_limit'
  | 'api_error'
  | 'tool_error'
  | 'unknown';

// ---------------------------------------------------------------------------
// Checkpoint Metadata
// ---------------------------------------------------------------------------

/**
 * Metadata stored with checkpoints for replay functionality.
 */
export interface CheckpointMetadata {
  failed_node?: string;
  failed_model?: string;
  error_message?: string;
  error_type?: FailureErrorType;
  provider?: string;
  created_at: string;
  parent_checkpoint_id?: string;
}

// ---------------------------------------------------------------------------
// Simplified Flow States (for simple/single-node flows)
// ---------------------------------------------------------------------------

/**
 * State for simple flows (single LLM call).
 */
export interface SimpleFlowState extends Omit<GraphState, 'turnNumber' | 'maxTurns' | 'currentModel' | 'confidenceScore' | 'consecutiveLowConfidenceTurns' | 'errorCount' | 'sameErrorCount' | 'noProgressTurns' | 'fileChanges' | 'escalations' | 'traversedNodes' | 'status'> {
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';
}

// ---------------------------------------------------------------------------
// Serialization Helpers
// ---------------------------------------------------------------------------

/**
 * Serialize state for DynamoDB storage.
 */
export function serializeState(state: GraphState): Record<string, unknown> {
  const serialized: Record<string, unknown> = { ...state };
  serialized.conversationHistory = JSON.stringify(state.conversationHistory);
  serialized.turns = JSON.stringify(state.turns);
  serialized.toolCalls = JSON.stringify(state.turns.flatMap(t => t.toolCalls));
  serialized.toolResults = JSON.stringify(state.turns.flatMap(t => t.toolResults));
  serialized.escalations = JSON.stringify(state.escalations);
  serialized.fileChanges = JSON.stringify(state.fileChanges);
  serialized.traversedNodes = JSON.stringify(state.traversedNodes);
  serialized.logBuffer = JSON.stringify(state.logBuffer);
  return serialized;
}

/**
 * Deserialize state from DynamoDB storage.
 */
export function deserializeState(data: Record<string, unknown>): GraphState {
  const state: GraphState = {
    channelId: data.channelId as string,
    executionId: data.executionId as string,
    initialPrompt: data.initialPrompt as string,
    flowType: data.flowType as FlowType,
    agentRole: data.agentRole as string | undefined,
    turnNumber: data.turnNumber as number,
    maxTurns: data.maxTurns as number,
    currentModel: data.currentModel as string,
    conversationHistory: typeof data.conversationHistory === 'string'
      ? JSON.parse(data.conversationHistory)
      : (data.conversationHistory as Message[]),
    turns: typeof data.turns === 'string'
      ? JSON.parse(data.turns)
      : (data.turns as ExecutionTurn[]),
    confidenceScore: data.confidenceScore as number,
    consecutiveLowConfidenceTurns: data.consecutiveLowConfidenceTurns as number,
    errorCount: data.errorCount as number,
    sameErrorCount: data.sameErrorCount as number,
    lastError: data.lastError as string | null,
    noProgressTurns: data.noProgressTurns as number,
    fileChanges: typeof data.fileChanges === 'string'
      ? JSON.parse(data.fileChanges)
      : (data.fileChanges as string[]),
    escalations: typeof data.escalations === 'string'
      ? JSON.parse(data.escalations)
      : (data.escalations as EscalationEvent[]),
    status: data.status as ExecutionStatus,
    abortRequested: data.abortRequested as boolean,
    totalInputTokens: data.totalInputTokens as number,
    totalOutputTokens: data.totalOutputTokens as number,
    finalResponse: data.finalResponse as string,
    traversedNodes: typeof data.traversedNodes === 'string'
      ? JSON.parse(data.traversedNodes)
      : (data.traversedNodes as string[]),
    logBuffer: typeof data.logBuffer === 'string'
      ? JSON.parse(data.logBuffer)
      : (data.logBuffer as LogEntry[]),
  };
  if (data.failureMetadata) {
    state.failureMetadata = typeof data.failureMetadata === 'string'
      ? JSON.parse(data.failureMetadata)
      : (data.failureMetadata as FailureMetadata);
  }
  return state;
}
