/**
 * ShellGraph - Single Node Flow
 *
 * A simple graph for shell command suggestions.
 * Uses tag-based routing: tier2 + general
 *
 * Flow: start → suggest → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { loadPrompt } from '../../../templates/loader';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions, MessageHistory } from './types';

const log = createLogger('GRAPH:SHELL');

// ============================================================================
// Graph State
// ============================================================================

interface ShellGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  message: string;
  history?: MessageHistory;
  workspaceId: string;
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
 * Suggest node - generates shell command suggestions using tier2 + general tags
 */
async function suggestNode(state: ShellGraphState): Promise<ShellGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('suggest');

  log.info(`ShellGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Tags: ${state.tags.join(', ')}`);

  try {
    // Load prompt from template
    const systemPrompt = loadPrompt('shell-command');

    // Format the full history with current message
    const fullHistory = state.history?.formatted_history
      ? `${state.history.formatted_history}\n\n${state.history.current_author}: ${state.history.current_message}`
      : `${state.message}`;

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Generate response using tag-based routing
    const response = await chatCompletion({
      model: 'auto',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: fullHistory },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
      metadata: {
        tags: state.tags,
      },
    });

    const content = extractContent(response);
    const modelUsed = response.model;
    log.info(`Shell flow complete, response length: ${content.length}, model: ${modelUsed}`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'suggest'],
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
      model: modelUsed,
      tags: state.tags,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);

    // Flush logs
    await logger.flush();

    return {
      ...state,
      model: modelUsed,
      response: content,
      status: 'complete',
      traversedNodes: ['start', 'suggest'],
    };
  } catch (error) {
    log.error(`ShellGraph error: ${error}`);

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

export function createShellGraph() {
  return {
    name: 'ShellGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking ShellGraph for channel ${options.channelId}`);

      // Use tier2 + general tags (from options or default)
      const tags = options.tags || ['tier2', 'general'];

      const initialState: ShellGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.SHELL,
        message: options.initialPrompt,
        history: options.history,
        workspaceId: options.workspacePath || options.channelId,
        tags,
        model: '',
        response: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      const finalState = await suggestNode(initialState);

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
export const shellGraph = createShellGraph();
