/**
 * SimpleGraph - Single Node Flow
 *
 * A simple graph for basic responses that don't require tools or complex processing.
 * This graph has a single processing node followed by a finalize node.
 *
 * Flow: start → respond → finalize
 *
 * @see plans/langgraph-migration-plan.md
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { getPromptForTaskType, getModelForTaskType } from '../../../templates/registry';
import { loadPrompt } from '../../../templates/loader';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:SIMPLE');

// ============================================================================
// Graph State
// ============================================================================

interface SimpleGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  taskType: string;
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Respond node - generates a simple response using the task type's prompt
 */
async function respondNode(state: SimpleGraphState): Promise<SimpleGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('respond');

  log.info(`SimpleGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Task type: ${state.taskType}`);

  try {
    // Get model and prompt for task type
    const model = getModelForTaskType(state.taskType as any);
    const promptCategory = getPromptForTaskType(state.taskType as any);
    const systemPrompt = loadPrompt(promptCategory);

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Using model: ${model}, temperature: ${params.temperature}`);

    // Generate response
    const response = await chatCompletion({
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: state.response },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
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
      taskType: state.taskType,
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
    log.error(`SimpleGraph error: ${error}`);

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

export function createSimpleGraph() {
  return {
    name: 'SimpleGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking SimpleGraph for channel ${options.channelId}`);

      const initialState: SimpleGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.SIMPLE,
        taskType: options.taskType || 'general',
        model: '',
        response: options.initialPrompt,
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
export const simpleGraph = createSimpleGraph();
