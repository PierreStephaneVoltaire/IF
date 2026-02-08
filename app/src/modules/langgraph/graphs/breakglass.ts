/**
 * BreakglassGraph - Single Node Flow
 *
 * A simple graph for direct model calls bypassing normal routing.
 * Uses tier4 + tools (highest quality) or user-specified model
 *
 * Flow: start → respond → finalize
 */

import { createLogger } from '../../../utils/logger';
import { executeSimpleTask } from '../../litellm/executor';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { loadPrompt } from '../../../templates/loader';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions, MessageHistory } from './types';

const log = createLogger('GRAPH:BREAKGLASS');

// ============================================================================
// Model Mapping (kept for backward compatibility)
// ============================================================================

const BREAKGLASS_MODEL_MAP: Record<string, string> = {
  'opus': 'claude-opus-4.5',
  'sonnet': 'claude-sonnet-4.5',
  'gemini': 'gemini-3-pro',
  'qwen': 'qwen3-max',
  'gpt': 'gpt-5.2-codex',
  'default': 'gemini-2.5-flash-lite',
  'glm': 'glm-4.7',
};

// ============================================================================
// Graph State
// ============================================================================

interface BreakglassGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  message: string;
  modelName: string;
  history?: MessageHistory;
  tags: string[];
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Respond node - generates response using specified breakglass model or tier4 + tools tags
 */
async function respondNode(state: BreakglassGraphState): Promise<BreakglassGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('respond');

  log.info(`BreakglassGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Breakglass model: ${state.modelName}`);
  log.info(`Tags: ${state.tags.join(', ')}`);

  try {
    // Map the model name to actual LiteLLM model string
    const actualModel = BREAKGLASS_MODEL_MAP[state.modelName.toLowerCase()];
    if (!actualModel) {
      throw new Error(`Invalid breakglass model: ${state.modelName}`);
    }

    log.info(`Using model: ${actualModel}`);

    // Load the breakglass template
    const systemPrompt = loadPrompt('breakglass');
    log.info(`Breakglass template loaded, length: ${systemPrompt.length}`);

    // Strip the @{modelname} prefix from the message
    const strippedMessage = state.message.replace(/^@\w+\s*/, '');
    log.info(`Stripped message: ${strippedMessage}`);

    // Format the user prompt with history and current message
    const historyText = state.history?.formatted_history || 'No previous messages.';
    const userPrompt = systemPrompt
      .replace('{{history}}', historyText)
      .replace('{{message}}', strippedMessage);

    log.info(`User prompt length: ${userPrompt.length}`);

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Call the model directly without tools (use tags for routing if actualModel is 'auto')
    const response = await executeSimpleTask(
      'breakglass',
      userPrompt,
      state.channelId,
      actualModel,
      false, // No tools for breakglass
      params
    );

    log.info(`Breakglass execution complete, response length: ${response.length}`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'respond'],
      turns: [],
      finalStatus: 'complete',
    });

    await logger.uploadMermaid(mermaidSource);
    const mermaidPng = await generator.renderPng(mermaidSource);
    await logger.uploadDiagramPng(mermaidPng);

    // Upload metadata
    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'complete',
      nodeCount: 2,
      model: actualModel,
      requestedModel: state.modelName,
      tags: state.tags,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);

    // Flush logs
    await logger.flush();

    return {
      ...state,
      model: actualModel,
      response,
      status: 'complete',
      traversedNodes: ['start', 'respond'],
    };
  } catch (error) {
    log.error(`BreakglassGraph error: ${error}`);

    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'error',
      error: String(error),
      tags: state.tags,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      status: 'error',
      response: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createBreakglassGraph() {
  return {
    name: 'BreakglassGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking BreakglassGraph for channel ${options.channelId}`);

      // Use tier4 + tools tags (highest quality) or from options
      const tags = options.tags || ['tier4', 'tools'];

      const initialState: BreakglassGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.BREAKGLASS,
        message: options.initialPrompt,
        modelName: options.modelName || 'default',
        history: options.history,
        tags,
        model: '',
        response: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      const finalState = await respondNode(initialState);

      return {
        response: finalState.response,
        model: finalState.model,
        traversedNodes: finalState.traversedNodes,
        error: finalState.status === 'error' ? finalState.response : undefined,
      };
    },
  };
}

// Export singleton
export const breakglassGraph = createBreakglassGraph();
