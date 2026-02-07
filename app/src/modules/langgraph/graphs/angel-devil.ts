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
import { MODEL_TIERS } from '../../agentic/escalation';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
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

      const angelPrompt = `You are the ANGEL - arguing the strongest possible case FOR the following question.

## User's Question
"${options.initialPrompt}"

## Your Role: THE ANGEL (Advocate FOR)
Your job is to make the strongest, most compelling case FOR this position.

## Guidelines
- Argue your side with full conviction
- Present the strongest ethical, practical, and emotional arguments FOR
- Use persuasive rhetoric and compelling examples
- Do not hedge - argue with passion

## Format
1. **Core Position**: Clear statement of what you're arguing FOR
2. **Ethical Arguments**: Why is this the morally right choice?
3. **Practical Benefits**: What good outcomes will result?
4. **Countering Objections**: Address the strongest arguments against`;

      const devilPrompt = `You are the DEVIL - arguing the strongest possible case AGAINST the following question.

## User's Question
"${options.initialPrompt}"

## Your Role: THE DEVIL (Advocate AGAINST)
Your job is to make the strongest, most compelling case AGAINST this position.

## Guidelines
- Argue your side with full conviction
- Present the strongest ethical, practical, and emotional arguments AGAINST
- Use persuasive rhetoric and cautionary examples
- Do not hedge - argue with passion

## Format
1. **Core Position**: Clear statement of what you're arguing AGAINST
2. **Ethical Concerns**: Why might this be the morally wrong choice?
3. **Risks and Downsides**: What negative outcomes could result?
4. **Countering Pro Arguments**: Address the strongest arguments for`;

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

      const judgePrompt = `You are a wise judge synthesizing a balanced, nuanced response from an angel/devil debate.

## User's Original Question
"${options.initialPrompt}"

## The Angel's Argument (FOR)
${angelArgument}

## The Devil's Argument (AGAINST)
${devilArgument}

## Your Task
Create a balanced synthesis that helps the user understand both sides.

## Format

### The Dilemma
Briefly frame what makes this a difficult choice

### The Case For (Angel's Perspective)
- Key point 1
- Key point 2
- Key point 3

### The Case Against (Devil's Perspective)
- Key point 1
- Key point 2
- Key point 3

### The Tension
What is the fundamental conflict? What values or priorities are in tension?

### Decision Framework
Help the user think through this by considering different priorities`;

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
