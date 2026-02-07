/**
 * ConsensusGraph - Parallel Flow
 *
 * A parallel graph for multi-source consensus on factual questions.
 * - 3 independent tier2 models answer independently
 * - 1 tier4 judge synthesizes consensus
 *
 * Flow: start → answer_1 → answer_2 → answer_3 → judge → finalize
 *
 * @see plans/langgraph-migration-plan.md
 */

import { createLogger } from '../../../utils/logger';
import { MODEL_TIERS } from '../../agentic/escalation';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:CONSENSUS');

// ============================================================================
// Helper Functions
// ============================================================================

function getRandomModelsFromTier(tier: keyof typeof MODEL_TIERS, count: number): string[] {
  const tierModels = [...MODEL_TIERS[tier]];
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

interface ConsensusGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
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

  const metadata = {
    flowType: state.flowType,
    channelId: state.channelId,
    executionId: state.executionId,
    status: 'complete',
    nodeCount: state.traversedNodes.length + 1,
    models: state.models,
    judgeModel: state.judgeModel,
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

      // Select models
      const models = getRandomModelsFromTier('tier2', 3);
      const judgeModel = getRandomModelFromTier('tier4');

      log.info(`Using independent models: ${models.join(', ')}`);
      log.info(`Using judge model: ${judgeModel}`);

      const params = getModelParams(FlowType.CONSENSUS);
      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      logger.recordNode('start');
      logger.recordNode('answer_1');
      logger.recordNode('answer_2');
      logger.recordNode('answer_3');

      const independentPrompt = `You are answering a factual question independently and thoroughly.

## User's Question
"${options.initialPrompt}"

## Your Task
Provide a complete, accurate answer to this factual question.

## Guidelines
- Answer as thoroughly and accurately as possible
- Base your answer on your training knowledge
- Include specific details, dates, numbers, or facts when relevant

## Format
1. **Direct Answer**: Clear answer to the question (1-3 sentences)
2. **Detailed Explanation**: Elaborate with supporting facts and context
3. **Confidence Level**: State your confidence (High/Medium/Low)`;

      // Execute answers in parallel
      const [response1, response2, response3] = await Promise.all([
        chatCompletion({
          model: models[0],
          messages: [{ role: 'user', content: independentPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
        }),
        chatCompletion({
          model: models[1],
          messages: [{ role: 'user', content: independentPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
        }),
        chatCompletion({
          model: models[2],
          messages: [{ role: 'user', content: independentPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
        }),
      ]);

      const answer1 = extractContent(response1);
      const answer2 = extractContent(response2);
      const answer3 = extractContent(response3);
      const answers = [answer1, answer2, answer3];

      log.info(`Independent answers generated: ${answer1.length}, ${answer2.length}, ${answer3.length} chars`);

      logger.recordNode('judge');

      const judgePrompt = `You are a fact-checking judge analyzing three independent answers to determine consensus.

## User's Original Question
"${options.initialPrompt}"

## Independent Answer 1 (from ${models[0]})
${answer1}

## Independent Answer 2 (from ${models[1]})
${answer2}

## Independent Answer 3 (from ${models[2]})
${answer3}

## Your Task
Analyze these three answers and synthesize a final response.

### Consensus Assessment
**Strong Consensus** / **Partial Consensus** / **Significant Disagreement**

### Agreed-Upon Facts
List facts that all three answers agree on

### Points of Disagreement
If answers disagree, clearly state the positions

### Synthesized Answer
Provide a clear, balanced answer`;

      const judgeResponse = await chatCompletion({
        model: judgeModel,
        messages: [{ role: 'user', content: judgePrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      });

      const consensus = extractContent(judgeResponse);
      log.info(`Consensus synthesized: ${consensus.length} chars`);

      const state: ConsensusGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.CONSENSUS,
        userQuestion: options.initialPrompt,
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
