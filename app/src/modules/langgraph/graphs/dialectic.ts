/**
 * DialecticGraph - Parallel Flow
 *
 * A parallel graph for philosophical exploration.
 * Uses tag-based routing:
 * - thesis/antithesis: tier2 + websearch (if websearch enabled)
 * - synthesizer: tier3 + thinking
 *
 * Flow: start → thesis → antithesis → synthesize → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:DIALECTIC');

// ============================================================================
// Graph State
// ============================================================================

interface DialecticGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  thesisTags: string[];
  antithesisTags: string[];
  synthesizerTags: string[];
  thesisModel: string;
  antithesisModel: string;
  synthesizerModel: string;
  thesis: string;
  antithesis: string;
  synthesis: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

async function thesisNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('thesis');

  log.info(`DialecticGraph: Generating thesis for channel ${state.channelId}`);
  log.info(`Tags: ${state.thesisTags.join(', ')}`);

  const params = getModelParams(state.flowType);

  const thesisPrompt = renderTemplate(loadPrompt('dialectic-thesis'), {
    user_question: state.userQuestion,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [{ role: 'user', content: thesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
    metadata: {
      tags: state.thesisTags,
    },
  });

  const thesis = extractContent(response);
  const modelUsed = response.model;
  log.info(`Thesis generated: ${thesis.length} chars, model: ${modelUsed}`);

  return {
    ...state,
    thesisModel: modelUsed,
    thesis,
    traversedNodes: ['start', 'thesis'],
  };
}

async function antithesisNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({ channelId: state.channelId, executionId: state.executionId });
  logger.recordNode('antithesis');

  log.info(`DialecticGraph: Generating antithesis`);
  log.info(`Tags: ${state.antithesisTags.join(', ')}`);

  const params = getModelParams(state.flowType);

  const antithesisPrompt = renderTemplate(loadPrompt('dialectic-antithesis'), {
    user_question: state.userQuestion,
    thesis: state.thesis,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [{ role: 'user', content: antithesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
    metadata: {
      tags: state.antithesisTags,
    },
  });

  const antithesis = extractContent(response);
  const modelUsed = response.model;
  log.info(`Antithesis generated: ${antithesis.length} chars, model: ${modelUsed}`);

  return {
    ...state,
    antithesisModel: modelUsed,
    antithesis,
    traversedNodes: [...state.traversedNodes, 'antithesis'],
  };
}

async function synthesizeNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({ channelId: state.channelId, executionId: state.executionId });
  logger.recordNode('synthesize');

  log.info(`DialecticGraph: Generating synthesis`);
  log.info(`Tags: ${state.synthesizerTags.join(', ')}`);

  const params = getModelParams(state.flowType);

  const synthesisPrompt = renderTemplate(loadPrompt('dialectic-synthesis'), {
    user_question: state.userQuestion,
    thesis: state.thesis,
    antithesis: state.antithesis,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [{ role: 'user', content: synthesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
    metadata: {
      tags: state.synthesizerTags,
    },
  });

  const synthesis = extractContent(response);
  const modelUsed = response.model;
  log.info(`Synthesis generated: ${synthesis.length} chars, model: ${modelUsed}`);

  return {
    ...state,
    synthesizerModel: modelUsed,
    synthesis,
    traversedNodes: [...state.traversedNodes, 'synthesize'],
  };
}

async function finalizeNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('finalize');

  // Generate Mermaid diagram
  const generator = getMermaidGenerator();
  const mermaidSource = generator.generate({
    flowType: state.flowType,
    traversedNodes: ['start', 'thesis', 'antithesis', 'synthesize', 'finalize'],
    turns: [],
    finalStatus: 'complete',
  });

  await logger.uploadMermaid(mermaidSource);
  const mermaidPng = await generator.renderPng(mermaidSource);
  await logger.uploadDiagramPng(mermaidPng);

  const metadata = {
    flowType: state.flowType,
    channelId: state.channelId,
    executionId: state.executionId,
    status: 'complete',
    nodeCount: 5,
    thesisModel: state.thesisModel,
    antithesisModel: state.antithesisModel,
    synthesizerModel: state.synthesizerModel,
    tags: state.synthesizerTags,
    timestamp: new Date().toISOString(),
  };

  await logger.uploadMetadata(metadata);
  await logger.flush();

  return {
    ...state,
    traversedNodes: [...state.traversedNodes, 'finalize'],
  };
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createDialecticGraph() {
  return {
    name: 'DialecticGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking DialecticGraph for channel ${options.channelId}`);

      // Use websearch tags if websearch is enabled
      const useWebsearch = options.websearch || false;
      const thesisTags = useWebsearch ? ['tier2', 'websearch'] : ['tier2', 'general'];
      const antithesisTags = useWebsearch ? ['tier2', 'websearch'] : ['tier2', 'general'];
      const synthesizerTags = ['tier3', 'thinking'];

      let state: DialecticGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.DIALECTIC,
        userQuestion: options.initialPrompt,
        thesisTags,
        antithesisTags,
        synthesizerTags,
        thesisModel: '',
        antithesisModel: '',
        synthesizerModel: '',
        thesis: '',
        antithesis: '',
        synthesis: '',
        status: 'running',
        traversedNodes: [],
      };

      // Execute sequential nodes
      state = await thesisNode(state);
      state = await antithesisNode(state);
      state = await synthesizeNode(state);
      state = await finalizeNode(state);

      return {
        response: state.synthesis,
        model: state.synthesizerModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.synthesis : undefined,
      };
    },
  };
}

// Export singleton
export const dialecticGraph = createDialecticGraph();
