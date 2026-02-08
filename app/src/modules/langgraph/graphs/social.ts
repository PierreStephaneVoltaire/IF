/**
 * SocialGraph - Single Node Flow
 *
 * A simple graph for social interactions, greetings, and casual chat.
 * Uses tag-based routing: tier1 + social
 *
 * Flow: start → respond → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { loadPrompt } from '../../../templates/loader';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions, MessageHistory } from './types';

const log = createLogger('GRAPH:SOCIAL');

// ============================================================================
// Graph State
// ============================================================================

interface SocialGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  message: string;
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
 * Respond node - generates a social response using tier1 + social tags
 */
async function respondNode(state: SocialGraphState): Promise<SocialGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('respond');

  log.info(`SocialGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Tags: ${state.tags.join(', ')}`);

  try {
    // Load prompt from template
    const systemPrompt = loadPrompt('social');

    // Get user message from state
    const userMessage = state.message;

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Generate response using tag-based routing
    const response = await chatCompletion({
      model: 'auto',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userMessage },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
      metadata: {
        tags: state.tags,
      },
    });

    const content = extractContent(response) || 'Hello!';
    const modelUsed = response.model;
    log.info(`Response generated: ${content.length} chars, model: ${modelUsed}`);

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
      traversedNodes: ['start', 'respond'],
    };
  } catch (error) {
    log.error(`SocialGraph error: ${error}`);

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

export function createSocialGraph() {
  return {
    name: 'SocialGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking SocialGraph for channel ${options.channelId}`);

      // Use tier1 + social tags (from options or default)
      const tags = options.tags || ['tier1', 'social'];

      const initialState: SocialGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.SOCIAL,
        message: options.initialPrompt,
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
export const socialGraph = createSocialGraph();
