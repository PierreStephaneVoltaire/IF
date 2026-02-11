/**
 * BranchGraph - Parallel Flow
 *
 * A parallel graph for exploring multiple architectural approaches.
 * Uses model group-based routing:
 * - Branch nodes: branch-tier3
 * - Aggregator: branch-tier4
 *
 * Flow: start → branch_1 → branch_2 → branch_3 → aggregate → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, tagsToModelGroup } from '../../litellm/index';
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
  branchModelGroup: string;
  aggregatorModelGroup: string;
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
  logger.recordNode('branch_1');
  logger.recordNode('branch_2');
  logger.recordNode('branch_3');

  log.info(`BranchGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Branch model group: ${state.branchModelGroup}`);
  log.info(`Aggregator model group: ${state.aggregatorModelGroup}`);

  try {
    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Load prompts
    const branchPrompt = renderTemplate(loadPrompt('branch-brainstorm'), {
      question: state.userQuestion,
    });

    const aggregatorPrompt = renderTemplate(loadPrompt('branch-aggregator'), {
      question: state.userQuestion,
      content_1: '', // Will be replaced with responses
      content_2: '',
      content_3: '',
    });

    // Execute branches in parallel with model group-based routing
    const [response1, response2, response3] = await Promise.all([
      chatCompletion({
        model: state.branchModelGroup,
        messages: [{ role: 'user', content: branchPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
      chatCompletion({
        model: state.branchModelGroup,
        messages: [{ role: 'user', content: branchPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
      chatCompletion({
        model: state.branchModelGroup,
        messages: [{ role: 'user', content: branchPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
    ]);

    const content1 = extractContent(response1);
    const content2 = extractContent(response2);
    const content3 = extractContent(response3);
    const model1 = response1.model;
    const model2 = response2.model;
    const model3 = response3.model;

    log.info(`Branch responses generated: ${content1.length}, ${content2.length}, ${content3.length} chars`);

    // Execute aggregator with model group-based routing
    const aggregatorResponse = await chatCompletion({
      model: state.aggregatorModelGroup,
      messages: [{ role: 'user', content: aggregatorPrompt }],
      temperature: params.temperature,
      top_p: params.top_p,
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
      nodeCount: 5,
      branchModels: [model1, model2, model3],
      aggregatorModel,
      modelGroup: state.aggregatorModelGroup,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      branchModels: [model1, model2, model3],
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
      modelGroup: state.branchModelGroup,
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

      // Get model groups from options, or convert tags if provided
      let branchModelGroup = options.modelGroup;
      let aggregatorModelGroup = 'branch-tier4';

      if (!branchModelGroup && options.tags && options.tags.length > 0) {
        const tags = options.tags;
        branchModelGroup = tagsToModelGroup(tags);
        // Aggregator is always tier higher
        aggregatorModelGroup = 'branch-tier4';
      }
      if (!branchModelGroup) {
        branchModelGroup = 'branch-tier3';
      }

      const initialState: BranchGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.BRANCH,
        userQuestion: options.initialPrompt,
        branchModelGroup,
        aggregatorModelGroup,
        branchModels: [],
        aggregatorModel: '',
        responses: [],
        finalResponse: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      const finalState = await branchNodes(initialState);

      return {
        response: finalState.finalResponse,
        model: finalState.aggregatorModel || finalState.branchModels[0] || 'branch-tier3',
        traversedNodes: finalState.traversedNodes,
        error: finalState.status === 'error' ? finalState.finalResponse : undefined,
      };
    },
  };
}

// Export singleton
export const branchGraph = createBranchGraph();
