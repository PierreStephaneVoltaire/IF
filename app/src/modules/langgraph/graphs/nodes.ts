/**
 * Common Node Functions for LangGraph
 *
 * Shared node implementations used across all flow graphs.
 * Provides logging, finalization, and common operation nodes.
 *
 * @see plans/langgraph-migration-plan.md
 */

import { createLogger } from '../../../utils/logger';
import { loadPrompt } from '../../../templates/loader';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import type { FlowType } from '../../litellm/types';
import type { ExecutionLogger } from '../logger';
import type { LogEntry } from '../state';
import type { GraphResult, MessageHistory } from './types';

const log = createLogger('GRAPH:NODES');

// ============================================================================
// Logging Helpers
// ============================================================================

export interface NodeContext {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  logger: ExecutionLogger;
  traversedNodes: string[];
  logBuffer: LogEntry[];
}

export function createNodeContext(
  channelId: string,
  executionId: string,
  flowType: FlowType,
  logger: ExecutionLogger
): NodeContext {
  return {
    channelId,
    executionId,
    flowType,
    logger,
    traversedNodes: [],
    logBuffer: [],
  };
}

export function enterNode(ctx: NodeContext, nodeName: string): void {
  ctx.traversedNodes.push(nodeName);
  ctx.logger.recordNode(nodeName);
  log.debug(`Entered node: ${nodeName}`);
}

export function logNode(ctx: NodeContext, level: LogEntry['level'], node: string, message: string, data?: unknown): void {
  ctx.logger.log(level, node, message, data);
}

export function logInfo(ctx: NodeContext, node: string, message: string, data?: unknown): void {
  logNode(ctx, 'INFO', node, message, data);
}

export function logError(ctx: NodeContext, node: string, message: string, data?: unknown): void {
  logNode(ctx, 'ERROR', node, message, data);
}

// ============================================================================
// Common LLM Operations
// ============================================================================

export interface SimpleLLMInput {
  systemPrompt: string;
  userMessage: string;
  model: string;
  flowType: FlowType;
  tags?: string[];
}

export async function simpleLLMCall(input: SimpleLLMInput): Promise<{ response: string; model: string }> {
  const params = getModelParams(input.flowType);
  log.info(`LLM call: model=${input.model}, temp=${params.temperature}, top_p=${params.top_p}`);

  const response = await chatCompletion({
    model: input.model,
    messages: [
      { role: 'system', content: input.systemPrompt },
      { role: 'user', content: input.userMessage },
    ],
    temperature: params.temperature,
    top_p: params.top_p,
    ...(input.tags ? { metadata: { tags: input.tags } } : {}),
  });

  const content = extractContent(response);
  return { response: content, model: input.model };
}

// ============================================================================
// Finalization Node
// ============================================================================

export interface FinalizeResult {
  response: string;
  model: string;
  traversedNodes: string[];
  traversedNodes_ignore: string[];
}

export async function finalizeGraph(
  ctx: NodeContext,
  response: string,
  model: string,
  status: 'complete' | 'error' = 'complete'
): Promise<FinalizeResult> {
  enterNode(ctx, 'finalize');

  try {
    // Generate and upload Mermaid diagram
    const { getMermaidGenerator } = await import('../mermaid');
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generateSummary({
      channelId: ctx.channelId,
      executionId: ctx.executionId,
      initialPrompt: '',
      flowType: ctx.flowType,
      turnNumber: 0,
      maxTurns: 0,
      currentModel: model,
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
      status: status === 'error' ? 'stuck' : status,
      abortRequested: false,
      totalInputTokens: 0,
      totalOutputTokens: 0,
      finalResponse: response,
      traversedNodes: ctx.traversedNodes,
      logBuffer: [],
    });

    await ctx.logger.uploadMermaid(mermaidSource);
    log.info('Mermaid diagram uploaded');

    // Upload metadata
    const metadata = {
      flowType: ctx.flowType,
      channelId: ctx.channelId,
      executionId: ctx.executionId,
      status,
      nodeCount: ctx.traversedNodes.length,
      model,
      timestamp: new Date().toISOString(),
    };

    await ctx.logger.uploadMetadata(metadata);
    log.info('Metadata uploaded');

    // Flush logs to S3
    await ctx.logger.flush();
    log.info('Execution logs flushed');

  } catch (error) {
    log.error('Error during graph finalization', { error });
    // Don't throw - we want to return the result even if logging fails
  }

  return {
    response,
    model,
    traversedNodes: ctx.traversedNodes,
    traversedNodes_ignore: ctx.traversedNodes,
  };
}

// ============================================================================
// Error Handler Node
// ============================================================================

export interface ErrorHandlerResult {
  response: string;
  model: string;
  error: string;
  failureMetadata: {
    failed_node: string;
    failed_model: string;
    error_type: 'unknown';
    error_message: string;
    provider: string;
    timestamp: string;
  };
  traversedNodes: string[];
  traversedNodes_ignore: string[];
}

export async function handleGraphError(
  ctx: NodeContext,
  nodeName: string,
  error: unknown,
  model: string,
  partialResponse?: string
): Promise<ErrorHandlerResult> {
  enterNode(ctx, 'error_handler');

  const errorMessage = error instanceof Error ? error.message : String(error);
  log.error(`Error in node ${nodeName}: ${errorMessage}`, { error });

  // Populate failure metadata
  const failureMetadata = {
    failed_node: nodeName,
    failed_model: model,
    error_type: 'unknown' as const,
    error_message: errorMessage,
    provider: extractProvider(model),
    timestamp: new Date().toISOString(),
  };

  // Try to finalize with error info
  const response = partialResponse || `An error occurred while processing your request: ${errorMessage}`;

  try {
    await finalizeGraph(ctx, response, model, 'error');
  } catch {
    // Finalization failed, but we still want to return the error info
  }

  return {
    response,
    model,
    error: errorMessage,
    failureMetadata,
    traversedNodes: ctx.traversedNodes,
    traversedNodes_ignore: ctx.traversedNodes,
  };
}

// ============================================================================
// Helper Functions
// ============================================================================

function extractProvider(model: string): string {
  const modelLower = model.toLowerCase();
  if (modelLower.includes('claude')) return 'anthropic';
  if (modelLower.includes('gpt') || modelLower.includes('openai')) return 'openai';
  if (modelLower.includes('gemini')) return 'google';
  if (modelLower.includes('qwen')) return 'alibaba';
  if (modelLower.includes('glm')) return '智谱AI';
  if (modelLower.includes('deepseek')) return 'deepseek';
  return 'unknown';
}

export function formatHistory(history: MessageHistory): string {
  if (history.formatted_history) {
    return `${history.formatted_history}\n\n${history.current_author}: ${history.current_message}`;
  }
  return `${history.current_author}: ${history.current_message}`;
}

// ============================================================================
// Simple Flow Node Factory
// ============================================================================

export interface SimpleFlowNodeInput {
  systemPromptKey: string;
  userMessage: string;
  model: string;
  flowType: FlowType;
}

export async function createSimpleFlowNode(
  ctx: NodeContext,
  nodeName: string,
  input: SimpleFlowNodeInput
): Promise<{ response: string; model: string }> {
  enterNode(ctx, nodeName);

  try {
    const systemPrompt = loadPrompt(input.systemPromptKey);
    const result = await simpleLLMCall({
      systemPrompt,
      userMessage: input.userMessage,
      model: input.model,
      flowType: input.flowType,
    });

    logInfo(ctx, nodeName, `Response generated: ${result.response.length} chars`);
    return result;
  } catch (error) {
    return await handleGraphError(ctx, nodeName, error, input.model);
  }
}
