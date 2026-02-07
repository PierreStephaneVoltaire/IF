/**
 * AngelDevilGraph - Parallel Flow
 *
 * A parallel graph for moral/ethical debate.
 * - Angel argues FOR, Devil argues AGAINST
 * - 2 tier2 models for adversarial debate
 * - 1 tier4 judge synthesizes balanced response
 *
 * Flow: start → angel → devil → judge → finalize
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

const log = createLogger('GRAPH:ANGEL_DEVIL');

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

interface AngelDevilGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  angelModel: string;
  devilModel: string;
  judgeModel: string;
  angelArgument: string;
  devilArgument: string;
  synthesis: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createAngelDevilGraph() {
  return {
    name: 'AngelDevilGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking AngelDevilGraph for channel ${options.channelId}`);

      // Select models
      const [angelModel, devilModel] = getRandomModelsFromTier('tier2', 2);
      const judgeModel = getRandomModelFromTier('tier4');

      log.info(`Using angel model: ${angelModel}`);
      log.info(`Using devil model: ${devilModel}`);
      log.info(`Using judge model: ${judgeModel}`);

      const params = getModelParams(FlowType.ANGEL_DEVIL);
      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      logger.recordNode('start');
      logger.recordNode('angel');
      logger.recordNode('devil');

      const angelPrompt = renderTemplate(loadPrompt('angel-devil-angel'), {
        user_question: options.initialPrompt,
      });

      const devilPrompt = renderTemplate(loadPrompt('angel-devil-devil'), {
        user_question: options.initialPrompt,
      });

      // Execute angel and devil in parallel
      const [angelResponse, devilResponse] = await Promise.all([
        chatCompletion({
          model: angelModel,
          messages: [{ role: 'user', content: angelPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
        }),
        chatCompletion({
          model: devilModel,
          messages: [{ role: 'user', content: devilPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
        }),
      ]);

      const angelArgument = extractContent(angelResponse);
      const devilArgument = extractContent(devilResponse);

      log.info(`Angel argument: ${angelArgument.length} chars`);
      log.info(`Devil argument: ${devilArgument.length} chars`);

      logger.recordNode('judge');

      const judgePrompt = renderTemplate(loadPrompt('angel-devil-judge'), {
        user_question: options.initialPrompt,
        angel_argument: angelArgument,
        devil_argument: devilArgument,
      });

      const judgeResponse = await chatCompletion({
        model: judgeModel,
        messages: [{ role: 'user', content: judgePrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      });

      const synthesis = extractContent(judgeResponse);
      log.info(`Balanced synthesis generated: ${synthesis.length} chars`);

      logger.recordNode('finalize');

      const generator = getMermaidGenerator();
      const mermaidSource = generator.generate({
        flowType: FlowType.ANGEL_DEVIL,
        traversedNodes: ['start', 'angel', 'devil', 'judge', 'finalize'],
        turns: [],
        finalStatus: 'complete',
      });

      await logger.uploadMermaid(mermaidSource);
      const mermaidPng = await generator.renderPng(mermaidSource);
      await logger.uploadDiagramPng(mermaidPng);

      const metadata = {
        flowType: FlowType.ANGEL_DEVIL,
        channelId: options.channelId,
        executionId: options.executionId,
        status: 'complete',
        nodeCount: 5,
        angelModel,
        devilModel,
        judgeModel,
        timestamp: new Date().toISOString(),
      };

      await logger.uploadMetadata(metadata);
      await logger.flush();

      return {
        response: synthesis,
        model: judgeModel,
        traversedNodes: ['start', 'angel', 'devil', 'judge', 'finalize'],
      };
    },
  };
}

// Export singleton
export const angelDevilGraph = createAngelDevilGraph();
