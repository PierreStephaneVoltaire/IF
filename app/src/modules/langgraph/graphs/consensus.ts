/**
 * ConsensusGraph - Parallel Flow
 *
 * A parallel graph for multi-source consensus on factual questions.
 * Uses tag-based routing:
 * - Independent answers: tier2 + general
 * - Judge: tier3 + thinking
 *
 * Flow: start → answer_1 → answer_2 → answer_3 → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:CONSENSUS');

// ============================================================================
// Graph State
// ============================================================================

interface ConsensusGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  answerTags: string[];
  judgeTags: string[];
  models: string[];
  judgeModel: string;
  answers: string[];
  consensus: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Finalize Helper
// ============================================================================

async function finalizeGraph(state: ConsensusGraphState): Promise<ConsensusGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('finalize');

  const generator = getMermaidGenerator();
  const mermaidSource = generator.generate({
    flowType: state.flowType,
    traversedNodes: [...state.traversedNodes, 'finalize'],
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
    nodeCount: state.traversedNodes.length + 1,
    models: state.models,
    judgeModel: state.judgeModel,
    tags: state.judgeTags,
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

export function createConsensusGraph() {
  return {
    name: 'ConsensusGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking ConsensusGraph for channel ${options.channelId}`);

      // Use tier2 for independent answers, tier3 + thinking for judge
      const answerTags = ['tier2', 'general'];
      const judgeTags = ['tier3', 'thinking'];

      const params = getModelParams(FlowType.CONSENSUS);
      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      logger.recordNode('start');
      logger.recordNode('answer_1');
      logger.recordNode('answer_2');
      logger.recordNode('answer_3');

      const independentPrompt = renderTemplate(loadPrompt('consensus-independent'), {
        user_question: options.initialPrompt,
      });

      // Execute answers in parallel with tag-based routing
      const [response1, response2, response3] = await Promise.all([
        chatCompletion({
          model: 'auto',
          messages: [{ role: 'user', content: independentPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
          metadata: { tags: answerTags },
        }),
        chatCompletion({
          model: 'auto',
          messages: [{ role: 'user', content: independentPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
          metadata: { tags: answerTags },
        }),
        chatCompletion({
          model: 'auto',
          messages: [{ role: 'user', content: independentPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
          metadata: { tags: answerTags },
        }),
      ]);

      const answer1 = extractContent(response1);
      const answer2 = extractContent(response2);
      const answer3 = extractContent(response3);
      const answers = [answer1, answer2, answer3];
      const models = [response1.model, response2.model, response3.model];

      log.info(`Independent answers generated: ${answer1.length}, ${answer2.length}, ${answer3.length} chars`);
      log.info(`Models used: ${models.join(', ')}`);

      logger.recordNode('judge');

      const judgePrompt = renderTemplate(loadPrompt('consensus-judge'), {
        user_question: options.initialPrompt,
        model_1: models[0],
        model_2: models[1],
        model_3: models[2],
        answer_1: answer1,
        answer_2: answer2,
        answer_3: answer3,
      });

      const judgeResponse = await chatCompletion({
        model: 'auto',
        messages: [{ role: 'user', content: judgePrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
        metadata: { tags: judgeTags },
      });

      const consensus = extractContent(judgeResponse);
      const judgeModel = judgeResponse.model;
      log.info(`Consensus synthesized: ${consensus.length} chars, judge model: ${judgeModel}`);

      const state: ConsensusGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.CONSENSUS,
        userQuestion: options.initialPrompt,
        answerTags,
        judgeTags,
        models,
        judgeModel,
        answers,
        consensus,
        status: 'complete',
        traversedNodes: ['start', 'answer_1', 'answer_2', 'answer_3', 'judge'],
      };

      await finalizeGraph(state);

      return {
        response: consensus,
        model: judgeModel,
        traversedNodes: state.traversedNodes,
      };
    },
  };
}

// Export singleton
export const consensusGraph = createConsensusGraph();
