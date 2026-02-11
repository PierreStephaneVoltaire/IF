/**
 * ConsensusGraph - Multi-Node Flow
 *
 * A graph for building consensus from multiple sources.
 * Uses model group-based routing:
 * - Answer nodes: consensus-tier2
 * - Judge: consensus-tier3
 *
 * Flow: start → answer_1 → answer_2 → answer_3 → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelGroup } from '../model-tiers';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt } from '../../../templates/loader';
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
  answerModelGroup: string;
  judgeModelGroup: string;
  models: string[];
  judgeModel: string;
  answers: string[];
  consensus: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Generate answers from multiple models
 */
async function generateAnswers(state: ConsensusGraphState): Promise<ConsensusGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('answer_1');
  logger.recordNode('answer_2');
  logger.recordNode('answer_3');

  log.info(`ConsensusGraph: Starting execution for channel ${state.channelId}`);

  try {
    const systemPrompt = loadPrompt('consensus-independent');
    const params = getModelParams(FlowType.CONSENSUS);

    const [response1, response2, response3] = await Promise.all([
      chatCompletion({
        model: state.answerModelGroup,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: state.userQuestion },
        ],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
      chatCompletion({
        model: state.answerModelGroup,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: state.userQuestion },
        ],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
      chatCompletion({
        model: state.answerModelGroup,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: state.userQuestion },
        ],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
    ]);

    const answers = [
      extractContent(response1),
      extractContent(response2),
      extractContent(response3),
    ];
    const models = [response1.model, response2.model, response3.model];

    log.info(`Generated ${answers.length} answers, total length: ${answers.join('\n---\n').length} chars`);

    return {
      ...state,
      answers,
      models,
      traversedNodes: ['start', 'answer_1', 'answer_2', 'answer_3'],
    };
  } catch (error) {
    log.error(`Consensus answer generation error: ${error}`);
    return {
      ...state,
      status: 'error',
      consensus: `Error generating answers: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Judge node - evaluates and synthesizes consensus
 */
async function judgeNode(state: ConsensusGraphState): Promise<ConsensusGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('judge');

  try {
    const systemPrompt = loadPrompt('consensus-judge');
    const params = getModelParams(FlowType.CONSENSUS);

    const combinedAnswers = state.answers
      .map((answer, i) => `Answer ${i + 1} (${state.models[i]}): ${answer}`)
      .join('\n\n');

    const response = await chatCompletion({
      model: state.judgeModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        {
          role: 'user',
          content: `${state.userQuestion}\n\n${combinedAnswers}`,
        },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const consensus = extractContent(response);
    const judgeModel = response.model;
    log.info(`Consensus generated: ${consensus.length} chars, model: ${judgeModel}`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'answer_1', 'answer_2', 'answer_3', 'judge'],
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
      judgeModel,
      models: state.models,
      answerModelGroup: state.answerModelGroup,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      consensus,
      judgeModel,
      status: 'complete',
      traversedNodes: [...state.traversedNodes, 'judge'],
    };
  } catch (error) {
    log.error(`Consensus judge error: ${error}`);
    return {
      ...state,
      status: 'error',
      consensus: `Error generating consensus: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createConsensusGraph() {
  return {
    name: 'ConsensusGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking ConsensusGraph for channel ${options.channelId}`);

      // Get model groups from options, or use new tiered system
      let answerModelGroup = options.modelGroup;
      if (!answerModelGroup && options.startingTier) {
        answerModelGroup = getModelGroup('consensus', options.startingTier as import('../model-tiers').Tier);
      }
      // Legacy fallback: convert tags if provided
      if (!answerModelGroup && options.tags && options.tags.length > 0) {
        const { tagsToModelGroup } = require('../../litellm/model-groups');
        answerModelGroup = tagsToModelGroup(options.tags);
      }
      if (!answerModelGroup) {
        answerModelGroup = 'consensus-tier2';
      }

      const initialState: ConsensusGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.CONSENSUS,
        userQuestion: options.initialPrompt,
        answerModelGroup,
        judgeModelGroup: 'consensus-tier3',
        models: [],
        judgeModel: '',
        answers: [],
        consensus: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      // Execute flow: answers → judge
      let state = await generateAnswers(initialState);
      if (state.status === 'error') {
        return { response: state.consensus, model: state.models[0] || 'consensus-tier2', traversedNodes: state.traversedNodes, error: state.consensus };
      }

      state = await judgeNode(state);

      return {
        response: state.consensus,
        model: state.judgeModel || state.models[0] || 'consensus-tier2',
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.consensus : undefined,
      };
    },
  };
}

// Export singleton
export const consensusGraph = createConsensusGraph();
