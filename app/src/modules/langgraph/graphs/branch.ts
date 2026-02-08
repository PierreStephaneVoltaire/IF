/**
 * BranchGraph - Parallel Flow
 *
 * A parallel graph for exploring multiple architectural approaches.
 * Uses tag-based routing:
 * - Branch nodes: tier3 + thinking
 * - Aggregator: tier4 + thinking
 *
 * Flow: start → branch_1 → branch_2 → branch_3 → aggregate → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:BRANCH');

// ============================================================================
// Graph State
// ============================================================================

interface BranchGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  branchTags: string[];
  aggregatorTags: string[];
  branchModels: string[];
  aggregatorModel: string;
  responses: string[];
  finalResponse: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Branch nodes - parallel exploration by multiple models
 */
async function branchNodes(state: BranchGraphState): Promise<BranchGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');

  log.info(`BranchGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Branch tags: ${state.branchTags.join(', ')}`);
  log.info(`Aggregator tags: ${state.aggregatorTags.join(', ')}`);

  try {
    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Brainstorming prompt
    const brainstormingPrompt = renderTemplate(loadPrompt('branch-brainstorm'), {
      user_question: state.userQuestion,
    });

    // Record branch nodes
    logger.recordNode('branch_1');
    logger.recordNode('branch_2');
    logger.recordNode('branch_3');

    // Execute branches in parallel with tag-based routing
    const [response1, response2, response3] = await Promise.all([
      chatCompletion({
        model: 'auto',
        messages: [{ role: 'user', content: brainstormingPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
        metadata: { tags: state.branchTags },
      }),
      chatCompletion({
        model: 'auto',
        messages: [{ role: 'user', content: brainstormingPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
        metadata: { tags: state.branchTags },
      }),
      chatCompletion({
        model: 'auto',
        messages: [{ role: 'user', content: brainstormingPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
        metadata: { tags: state.branchTags },
      }),
    ]);

    const content1 = extractContent(response1);
    const content2 = extractContent(response2);
    const content3 = extractContent(response3);
    const branchModels = [response1.model, response2.model, response3.model];

    log.info(`Branch responses generated: ${content1.length}, ${content2.length}, ${content3.length} chars`);
    log.info(`Branch models: ${branchModels.join(', ')}`);

    // Record aggregate node
    logger.recordNode('aggregate');

    // Aggregator prompt
    const aggregatorPrompt = renderTemplate(loadPrompt('branch-aggregator'), {
      user_question: state.userQuestion,
      model_1: branchModels[0],
      model_2: branchModels[1],
      model_3: branchModels[2],
      content_1: content1,
      content_2: content2,
      content_3: content3,
    });

    // Execute aggregator with tag-based routing
    const aggregatorResponse = await chatCompletion({
      model: 'auto',
      messages: [{ role: 'user', content: aggregatorPrompt }],
      temperature: params.temperature,
      top_p: params.top_p,
      metadata: { tags: state.aggregatorTags },
    });

    const aggregatorContent = extractContent(aggregatorResponse);
    const aggregatorModel = aggregatorResponse.model;
    log.info(`Aggregator response generated: ${aggregatorContent.length} chars, model: ${aggregatorModel}`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'branch_1', 'branch_2', 'branch_3', 'aggregate'],
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
      nodeCount: 5,
      branchModels,
      aggregatorModel,
      tags: state.aggregatorTags,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);

    // Flush logs
    await logger.flush();

    return {
      ...state,
      branchModels,
      aggregatorModel,
      responses: [content1, content2, content3],
      finalResponse: aggregatorContent,
      status: 'complete',
      traversedNodes: ['start', 'branch_1', 'branch_2', 'branch_3', 'aggregate'],
    };
  } catch (error) {
    log.error(`BranchGraph error: ${error}`);

    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'error',
      error: String(error),
      tags: state.branchTags,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      status: 'error',
      finalResponse: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createBranchGraph() {
  return {
    name: 'BranchGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking BranchGraph for channel ${options.channelId}`);

      // Use tier3 + thinking for branches, tier4 + thinking for aggregator
      const branchTags = ['tier3', 'thinking'];
      const aggregatorTags = ['tier4', 'thinking'];

      const initialState: BranchGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.BRANCH,
        userQuestion: options.initialPrompt,
        branchTags,
        aggregatorTags,
        branchModels: [],
        aggregatorModel: '',
        responses: [],
        finalResponse: '',
        status: 'running',
        traversedNodes: [],
      };

      const finalState = await branchNodes(initialState);

      return {
        response: finalState.finalResponse,
        model: finalState.aggregatorModel,
        traversedNodes: finalState.traversedNodes,
        error: finalState.status === 'error' ? finalState.finalResponse : undefined,
      };
    },
  };
}

// Export singleton
export const branchGraph = createBranchGraph();
