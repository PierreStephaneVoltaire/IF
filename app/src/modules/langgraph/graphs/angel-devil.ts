/**
 * AngelDevilGraph - Parallel Flow
 *
 * A parallel graph for moral/ethical debate.
 * Uses tag-based routing:
 * - Angel/Devil: tier2 + general
 * - Judge: tier3 + thinking
 *
 * Flow: start → angel → devil → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:ANGEL_DEVIL');

// ============================================================================
// Graph State
// ============================================================================

interface AngelDevilGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  debateTags: string[];
  judgeTags: string[];
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

      // Use tier2 for angel/devil, tier3 + thinking for judge
      const debateTags = ['tier2', 'general'];
      const judgeTags = ['tier3', 'thinking'];

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

      // Execute angel and devil in parallel with tag-based routing
      const [angelResponse, devilResponse] = await Promise.all([
        chatCompletion({
          model: 'auto',
          messages: [{ role: 'user', content: angelPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
          metadata: { tags: debateTags },
        }),
        chatCompletion({
          model: 'auto',
          messages: [{ role: 'user', content: devilPrompt }],
          temperature: params.temperature,
          top_p: params.top_p,
          metadata: { tags: debateTags },
        }),
      ]);

      const angelArgument = extractContent(angelResponse);
      const devilArgument = extractContent(devilResponse);
      const angelModel = angelResponse.model;
      const devilModel = devilResponse.model;

      log.info(`Angel argument: ${angelArgument.length} chars, model: ${angelModel}`);
      log.info(`Devil argument: ${devilArgument.length} chars, model: ${devilModel}`);

      logger.recordNode('judge');

      const judgePrompt = renderTemplate(loadPrompt('angel-devil-judge'), {
        user_question: options.initialPrompt,
        angel_argument: angelArgument,
        devil_argument: devilArgument,
      });

      const judgeResponse = await chatCompletion({
        model: 'auto',
        messages: [{ role: 'user', content: judgePrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
        metadata: { tags: judgeTags },
      });

      const synthesis = extractContent(judgeResponse);
      const judgeModel = judgeResponse.model;
      log.info(`Balanced synthesis generated: ${synthesis.length} chars, judge model: ${judgeModel}`);

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
        tags: judgeTags,
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
