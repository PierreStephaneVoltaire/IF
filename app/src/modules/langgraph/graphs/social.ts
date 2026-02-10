/**
 * SocialGraph - Single Node Flow
 *
 * A simple graph for social interactions, greetings, and casual chat.
 * Uses model group-based routing: general-tier1
 *
 * Flow: start → respond → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelGroup } from '../model-tiers';
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
  modelGroup: string;
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Respond node - generates a social response using general-tier1 model group
 */
async function respondNode(state: SocialGraphState): Promise<SocialGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('respond');

  log.info(`SocialGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Model Group: ${state.modelGroup}`);

  try {
    // Load prompt from template
    const systemPrompt = loadPrompt('social');

    // Get user message from state
    const userMessage = state.message;

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Generate response using model group-based routing
    const response = await chatCompletion({
      model: state.modelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userMessage },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
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

    // Try to render PNG, but don't let it fail the whole request
    try {
      const mermaidPng = await generator.renderPng(mermaidSource);
      await logger.uploadDiagramPng(mermaidPng);
    } catch (diagramError) {
      log.warn(`Failed to render Mermaid diagram: ${diagramError}`);
      // Continue - diagram is optional, user still gets their response
    }

    // Upload metadata
    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'complete',
      nodeCount: 2,
      model: modelUsed,
      modelGroup: state.modelGroup,
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
      modelGroup: state.modelGroup,
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

      // Get modelGroup from options, or use new tiered system
      let modelGroup = options.modelGroup;
      if (!modelGroup) {
        // Social is always tier1
        modelGroup = getModelGroup('social', 'tier1');
      }
      // Legacy fallback: convert tags if provided
      if (!modelGroup && options.tags && options.tags.length > 0) {
        const { tagsToModelGroup } = require('../../litellm/model-groups');
        modelGroup = tagsToModelGroup(options.tags);
      }
      if (!modelGroup) {
        modelGroup = 'social-tier1';
      }

      const initialState: SocialGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.SOCIAL,
        message: options.initialPrompt,
        history: options.history,
        modelGroup,
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
