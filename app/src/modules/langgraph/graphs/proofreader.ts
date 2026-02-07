/**
 * ProofreaderGraph - Single Node Flow
 *
 * A simple graph for grammar and spellcheck only.
 * - Always uses Tier 1 models (cheapest, fastest)
 * - ONLY fixes grammar and spelling
 * - NEVER alters the intent, tone, or style unless explicitly requested
 * - Preserves the user's voice and message meaning
 *
 * Flow: start → proofread → finalize
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
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Proofread node - generates grammar/spellcheck response using tier 1 model
 */
async function proofreadNode(state: ProofreaderGraphState): Promise<ProofreaderGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('proofread');

  log.info(`ProofreaderGraph: Starting execution for channel ${state.channelId}`);

  try {
    // Always use tier 1 model for proofreading
    const model = getModelFromTier('tier1', 0);
    log.info(`Using tier 1 model for proofreading: ${model}`);

    // Load prompt from template
    const systemPrompt = loadPrompt('proofreader');

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

    const content = extractContent(response) || 'No errors found.';
    log.info(`Response generated: ${content.length} chars`);

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

      const initialState: ProofreaderGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.PROOFREADER,
        message: options.initialPrompt,
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
