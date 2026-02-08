/**
 * SimpleGraph - Single Node Flow
 *
 * A simple graph for basic responses that don't require tools or complex processing.
 * Uses tag-based model routing via LiteLLM.
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
 * Respond node - generates a simple response using tags for model routing
 */
async function respondNode(state: SimpleGraphState): Promise<SimpleGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('respond');

  log.info(`SimpleGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Tags: ${state.tags.join(', ')}`);

  try {
    // Load prompt from template
    const promptCategory = getPromptForTaskType(state.taskType);
    const systemPrompt = loadPrompt(promptCategory);

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Using tags: ${state.tags.join(', ')}, temperature: ${params.temperature}`);

    // Generate response using tag-based routing
    const response = await chatCompletion({
      model: 'auto',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: state.response },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
      metadata: {
        tags: state.tags,
      },
    });

    const content = extractContent(response);
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
      taskType: state.taskType,
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
    log.error(`SimpleGraph error: ${error}`);

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
// Helper Functions
// ============================================================================

function getPromptForTaskType(taskType: string): string {
  const promptMap: Record<string, string> = {
    'technical-qa': 'technical-qa',
    'architecture-analysis': 'architecture-analysis',
    'doc-search': 'doc-search',
    'explanation': 'explanation',
    'social': 'social',
    'general-convo': 'general',
    'writing': 'general',
    'shell-command': 'shell-command',
  };
  return promptMap[taskType] || 'general';
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createSimpleGraph() {
  return {
    name: 'SimpleGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking SimpleGraph for channel ${options.channelId}`);

      // Get tags from options, default to tier2 + general
      const tags = options.tags || ['tier2', 'general'];

      const initialState: SimpleGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.SIMPLE,
        taskType: options.taskType || 'general',
        tags,
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
