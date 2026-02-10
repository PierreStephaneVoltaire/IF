/**
 * ProofreaderGraph - Single Node Flow
 *
 * A simple graph for grammar and spellcheck only.
 * Uses model group-based routing: general-tier1
 *
 * Flow: start → proofread → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelGroup } from '../model-tiers';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { loadPrompt } from '../../../templates/loader';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:PROOFREADER');

// ============================================================================
// Graph State
// ============================================================================

interface ProofreaderGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  message: string;
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
 * Proofread node - generates grammar/spellcheck response using general-tier1 model group
 */
async function proofreadNode(state: ProofreaderGraphState): Promise<ProofreaderGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('proofread');

  log.info(`ProofreaderGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Model Group: ${state.modelGroup}`);

  try {
    // Load prompt from template
    const systemPrompt = loadPrompt('proofreader');

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

    const content = extractContent(response) || 'No errors found.';
    const modelUsed = response.model;
    log.info(`Response generated: ${content.length} chars, model: ${modelUsed}`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'proofread'],
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
      traversedNodes: ['start', 'proofread'],
    };
  } catch (error) {
    log.error(`ProofreaderGraph error: ${error}`);

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

export function createProofreaderGraph() {
  return {
    name: 'ProofreaderGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking ProofreaderGraph for channel ${options.channelId}`);

      // Get modelGroup from options, or use new tiered system
      let modelGroup = options.modelGroup;
      if (!modelGroup) {
        // Proofreader is always tier1
        modelGroup = getModelGroup('proofreader', 'tier1');
      }
      // Legacy fallback: convert tags if provided
      if (!modelGroup && options.tags && options.tags.length > 0) {
        const { tagsToModelGroup } = require('../../litellm/model-groups');
        modelGroup = tagsToModelGroup(options.tags);
      }
      if (!modelGroup) {
        modelGroup = 'proofreader-tier1';
      }

      const initialState: ProofreaderGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.PROOFREADER,
        message: options.initialPrompt,
        modelGroup,
        model: '',
        response: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      const finalState = await proofreadNode(initialState);

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
export const proofreaderGraph = createProofreaderGraph();
