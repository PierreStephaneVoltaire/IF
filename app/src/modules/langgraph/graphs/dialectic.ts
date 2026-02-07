/**
 * DialecticGraph - Parallel Flow
 *
 * A parallel graph for philosophical exploration.
 * - Thesis → Antithesis → Synthesis
 * - 2 tier2 models for thesis/antithesis
 * - 1 tier4 synthesizer
 *
 * Flow: start → thesis → antithesis → synthesize → finalize
 *
 * @see plans/langgraph-migration-plan.md
 */

import { createLogger } from '../../../utils/logger';
import { MODEL_TIERS } from '../model-tiers';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:DIALECTIC');

// ============================================================================
// Helper Functions
// ============================================================================

function getRandomModelsFromTier(tier: keyof typeof MODEL_TIERS, count: number): string[] {
  const tierModels = [...MODEL_TIERS[tier]];
  // Shuffle array
  for (let i = tierModels.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [tierModels[i], tierModels[j]] = [tierModels[j], tierModels[i]];
  }
  return tierModels.slice(0, Math.min(count, tierModels.length));
}

function getRandomModelFromTier(tier: keyof typeof MODEL_TIERS): string {
  const tierModels = MODEL_TIERS[tier];
  const randomIndex = Math.floor(Math.random() * tierModels.length);
  return tierModels[randomIndex];
}

// ============================================================================
// Graph State
// ============================================================================

interface DialecticGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
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

  const params = getModelParams(state.flowType);

  const thesisPrompt = renderTemplate(loadPrompt('dialectic-thesis'), {
    user_question: state.userQuestion,
  });

  const response = await chatCompletion({
    model: state.thesisModel,
    messages: [{ role: 'user', content: thesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const thesis = extractContent(response);
  log.info(`Thesis generated: ${thesis.length} chars`);

  return {
    ...state,
    thesis,
    traversedNodes: ['start', 'thesis'],
  };
}

async function antithesisNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({ channelId: state.channelId, executionId: state.executionId });
  logger.recordNode('antithesis');

  log.info(`DialecticGraph: Generating antithesis`);

  const params = getModelParams(state.flowType);

  const antithesisPrompt = renderTemplate(loadPrompt('dialectic-antithesis'), {
    user_question: state.userQuestion,
    thesis: state.thesis,
  });

  const response = await chatCompletion({
    model: state.antithesisModel,
    messages: [{ role: 'user', content: antithesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const antithesis = extractContent(response);
  log.info(`Antithesis generated: ${antithesis.length} chars`);

  return {
    ...state,
    antithesis,
    traversedNodes: [...state.traversedNodes, 'antithesis'],
  };
}

async function synthesizeNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({ channelId: state.channelId, executionId: state.executionId });
  logger.recordNode('synthesize');

  log.info(`DialecticGraph: Generating synthesis`);

  const params = getModelParams(state.flowType);

  const synthesisPrompt = renderTemplate(loadPrompt('dialectic-synthesis'), {
    user_question: state.userQuestion,
    thesis: state.thesis,
    antithesis: state.antithesis,
  });

  const response = await chatCompletion({
    model: state.synthesizerModel,
    messages: [{ role: 'user', content: synthesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const synthesis = extractContent(response);
  log.info(`Synthesis generated: ${synthesis.length} chars`);

  return {
    ...state,
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

      // Select models
      const [thesisModel, antithesisModel] = getRandomModelsFromTier('tier2', 2);
      const synthesizerModel = getRandomModelFromTier('tier4');

      log.info(`Using thesis model: ${thesisModel}`);
      log.info(`Using antithesis model: ${antithesisModel}`);
      log.info(`Using synthesizer model: ${synthesizerModel}`);

      let state: DialecticGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.DIALECTIC,
        userQuestion: options.initialPrompt,
        thesisModel,
        antithesisModel,
        synthesizerModel,
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
