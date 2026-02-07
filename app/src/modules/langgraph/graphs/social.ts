/**
 * SocialGraph - Single Node Flow
 *
 * A simple graph for social interactions, greetings, and casual chat.
 * - Always uses Tier 1 models (cheapest, fastest)
 * - No tools, no planning
 * - Quick responses
 *
 * Flow: start → respond → finalize
 *
 * @see plans/langgraph-migration-plan.md
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { getModelFromTier } from '../../../templates/registry';
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
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Respond node - generates a social response using tier 1 model
 */
async function respondNode(state: SocialGraphState): Promise<SocialGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('respond');

  log.info(`SocialGraph: Starting execution for channel ${state.channelId}`);

  try {
    // Always use tier 1 model for social interactions
    const model = getModelFromTier('tier1', 0);
    log.info(`Using tier 1 model for social: ${model}`);

    // Load prompt from template
    const systemPrompt = loadPrompt('social');

    // Get user message from state
    const userMessage = state.message;

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Generate response
    const response = await chatCompletion({
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userMessage },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response) || 'Hello!';
    log.info(`Response generated: ${content.length} chars`);

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
      model,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);

    // Flush logs
    await logger.flush();

    return {
      ...state,
      model,
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

      const initialState: SocialGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.SOCIAL,
        message: options.initialPrompt,
        history: options.history,
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
