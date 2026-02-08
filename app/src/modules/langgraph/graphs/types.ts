/**
 * LangGraph Types
 *
 * Shared types for all LangGraph node definitions.
 * These types extend the base graph state with flow-specific state.
 *
 * @see plans/langgraph-migration-plan.md
 */

import type { FlowType, TaskType } from '../../litellm/types';
import type { GraphState, ExecutionTurn, LogEntry, FailureMetadata } from '../state';

// ============================================================================
// Graph Result Types
// ============================================================================

export interface GraphResult {
  response: string;
  model: string;
  traversedNodes: string[];
  error?: string;
  failureMetadata?: FailureMetadata;
}

export interface GraphInvokeOptions {
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  agentRole?: string;
  taskType?: string;
  modelName?: string; // For breakglass
  workspacePath?: string;
  history?: MessageHistory;
  // New properties for dynamic model selection
  startingTier?: 'tier1' | 'tier2' | 'tier3' | 'tier4';
  tags?: string[];
  websearch?: boolean;
}

export interface MessageHistory {
  formatted_history: string;
  current_author: string;
  current_message: string;
  current_attachments?: {
    images: Array<{ url: string; filename: string; content_type?: string }>;
    textFiles: Array<{ url: string; filename: string; content_type?: string }>;
    otherFiles: Array<{ url: string; filename: string; content_type?: string }>;
  };
  poll_entries?: Array<{
    question: string;
    options: Array<{ id: string; label: string; description: string }>;
    selectedOption: string;
    selectedBy: { id: string; username: string };
    timestamp: string;
  }>;
}

// ============================================================================
// Simple Flow State
// ============================================================================

export interface SimpleGraphState {
  // Input
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  taskType: string;

  // Execution
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';

  // Logging & Diagrams
  traversedNodes: string[];
  logBuffer: LogEntry[];

  // Error tracking
  failureMetadata?: FailureMetadata;
}

// ============================================================================
// Parallel Flow State (Branch, Consensus, Angel-Devil)
// ============================================================================

export interface ParallelGraphState {
  // Input
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  userQuestion: string;

  // Parallel models
  models: string[];
  responses: string[];

  // Aggregator/Judge
  aggregatorModel: string;
  finalResponse: string;

  // Status
  status: 'running' | 'complete' | 'error';

  // Logging & Diagrams
  traversedNodes: string[];
  logBuffer: LogEntry[];

  // Error tracking
  failureMetadata?: FailureMetadata;
}

// ============================================================================
// Dialectic Flow State (Thesis → Antithesis → Synthesis)
// ============================================================================

export interface DialecticGraphState {
  // Input
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  userQuestion: string;

  // Models
  thesisModel: string;
  antithesisModel: string;
  synthesizerModel: string;

  // Responses
  thesis: string;
  antithesis: string;
  synthesis: string;

  // Status
  status: 'running' | 'complete' | 'error';

  // Logging & Diagrams
  traversedNodes: string[];
  logBuffer: LogEntry[];

  // Error tracking
  failureMetadata?: FailureMetadata;
}

// ============================================================================
// Architecture Flow State
// ============================================================================

export interface ArchitectureGraphState {
  // Input
  channelId: string;
  executionId: string;
  initialPrompt: string;
  flowType: FlowType;
  workspacePath: string;
  history: MessageHistory;

  // Planning
  planningResult?: {
    reformulated_prompt: string;
    topic_slug: string;
    plan_content: string;
    instruction_content: string;
    task_type: TaskType;
    agent_role: string;
    complexity: string;
    estimated_turns: number;
    confidence_assessment: {
      has_progress: boolean;
      score: number;
      reasoning: string;
    };
  };

  // Execution
  model: string;
  response: string;
  confidenceScore: number;

  // Status
  status: 'running' | 'complete' | 'error';

  // Logging & Diagrams
  traversedNodes: string[];
  logBuffer: LogEntry[];

  // Error tracking
  failureMetadata?: FailureMetadata;
}

// ============================================================================
// Sequential Thinking Flow State (Complex Multi-Node)
// ============================================================================

export interface SequentialGraphState extends GraphState {
  // All GraphState fields are already included

  // Additional tracking for sequential thinking
  checkpointInterval: number;
  lastCheckpointTurn: number;

  // Reflexion
  reflectionResult?: {
    what_worked: string;
    what_failed: string;
    root_cause: string;
    strategy_change: string;
    key_insight: string;
  };
}
