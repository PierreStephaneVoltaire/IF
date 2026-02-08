/**
 * AdversarialValidationGraph - Adversarial Flow
 *
 * An adversarial validation flow for security evaluations, architecture hardening,
 * and design reviews. Uses a generator/red-team/judge pattern:
 * - Generator (tier2): Creates initial solution/design
 * - Red Team (tier3): Attacks/finds flaws
 * - Generator: Reviews and patches
 * - Red Team: Re-attacks
 * - Repeat for max rounds
 * - Judge (tier3): Validates final solution
 *
 * Flow: start → improve_prompt → generator → redteam_1 → generator_patch → redteam_2 → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import { getReflectionTags, escalateTier } from '../model-tiers';
import type { GraphResult, GraphInvokeOptions } from './types';
import type { Message, LogEntry } from '../state';

const log = createLogger('GRAPH:ADVERSARIAL');

const DEFAULT_MAX_ROUNDS = 3;

// ============================================================================
// Graph State
// ============================================================================

interface AdversarialGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  initialPrompt: string;
  clarifiedPrompt: string;
  generatorTags: string[];
  redteamTags: string[];
  judgeTags: string[];
  generatorModel: string;
  redteamModel: string;
  judgeModel: string;
  improvedPrompt: string;
  generatorResponse: string;
  generatorResponses: string[];  // NEW: All generator responses across rounds
  redteamFindings: string[];
  patches: string[];
  roundNumber: number;
  maxRounds: number;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
  logBuffer: LogEntry[];
  judgeVerdict: string;  // NEW: Final judge verdict
}

// ============================================================================
// Helper Functions
// ============================================================================

async function improvePrompt(initialPrompt: string, tags: string[]): Promise<string> {
  const systemPrompt = await loadPrompt('general');
  const userPrompt = renderTemplate(await loadPrompt('adversarial-improve-prompt'), {
    initial_prompt: initialPrompt,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || initialPrompt;
}

async function generateSolution(prompt: string, tags: string[]): Promise<string> {
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'user', content: prompt },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || 'No solution generated';
}

async function redTeamAttack(solution: string, prompt: string, tags: string[]): Promise<string> {
  const systemPrompt = await loadPrompt('adversarial-redteam');
  const userPrompt = renderTemplate(await loadPrompt('adversarial-redteam-user'), {
    original_prompt: prompt,
    proposed_solution: solution,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.9,
    top_p: 0.95,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || 'No findings generated';
}

async function patchSolution(solution: string, findings: string, tags: string[]): Promise<string> {
  const systemPrompt = await loadPrompt('adversarial-generator');
  const userPrompt = renderTemplate(await loadPrompt('adversarial-patch-user'), {
    clarified_prompt: '',
    redteam_findings: findings,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: `Original Solution:\n${solution}\n\n${userPrompt}` },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || solution;
}

async function judgeValidation(
  originalPrompt: string,
  improvedPrompt: string,
  generatorResponses: string[],
  redteamFindings: string[],
  patches: string[],
  tags: string[]
): Promise<string> {
  const history = generatorResponses.map((resp, i) =>
    `Round ${i + 1} Solution:\n${resp}\n\nRed Team Findings:\n${redteamFindings[i]}\n\nPatch:\n${patches[i]}\n`
  ).join('\n---\n');

  const systemPrompt = await loadPrompt('adversarial-judge');
  const userPrompt = renderTemplate(await loadPrompt('adversarial-judge-user'), {
    original_prompt: originalPrompt,
    improved_prompt: improvedPrompt,
    adversarial_history: history,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.6,
    top_p: 0.85,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || 'Validation complete. Review required.';
}

async function finalizeGraph(state: AdversarialGraphState): Promise<GraphResult> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('finalize');

  const generator = getMermaidGenerator();
  const mermaidSource = generator.generate({
    flowType: state.flowType,
    traversedNodes: state.traversedNodes,
    turns: [],
    finalStatus: 'complete',
  });

  await logger.uploadMermaid(mermaidSource);
  const mermaidPng = await generator.renderPng(mermaidSource);
  await logger.uploadDiagramPng(mermaidPng);

  const finalResponse = `## Adversarial Validation Complete\n\n**Original Request:** ${state.initialPrompt}\n\n**Clarified Request:** ${state.clarifiedPrompt}\n\n**Rounds:** ${state.roundNumber}\n\n### Generator Solutions:\n${state.generatorResponses?.map((r, i) => `**Round ${i + 1}:**\n${r}`).join('\n\n') || state.generatorResponse}\n\n### Red Team Findings:\n${state.redteamFindings?.map((f, i) => `**Round ${i + 1}:**\n${f}`).join('\n\n') || 'N/A'}\n\n### Patches:\n${state.patches?.map((p, i) => `**Round ${i + 1}:**\n${p}`).join('\n\n') || 'N/A'}\n\n**Final Judge Verdict:**\n${state.judgeVerdict || 'Pending validation'}\n\n**Status:** ${state.status}`;

  const metadata = {
    flowType: state.flowType,
    channelId: state.channelId,
    executionId: state.executionId,
    status: 'complete',
    nodeCount: state.traversedNodes.length + 1,
    model: state.judgeModel,
    tags: state.judgeTags,
    rounds: state.roundNumber,
    timestamp: new Date().toISOString(),
  };

  await logger.uploadMetadata(metadata);
  await logger.flush();

  return {
    response: finalResponse,
    model: state.judgeModel,
    traversedNodes: state.traversedNodes,
  };
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createAdversarialGraph() {
  return {
    name: 'AdversarialValidationGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking AdversarialValidationGraph for channel ${options.channelId}`);

      const state: AdversarialGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.ADVERSARIAL_VALIDATION,
        initialPrompt: options.initialPrompt,
        clarifiedPrompt: '',
        generatorTags: ['tier2', 'general'],
        redteamTags: ['tier3', 'thinking'],
        judgeTags: ['tier3', 'thinking'],
        generatorModel: 'auto',
        redteamModel: 'auto',
        judgeModel: 'auto',
        improvedPrompt: '',
        generatorResponse: '',
        generatorResponses: [],
        redteamFindings: [],
        patches: [],
        roundNumber: 0,
        maxRounds: DEFAULT_MAX_ROUNDS,
        status: 'running',
        traversedNodes: [],
        logBuffer: [],
        judgeVerdict: '',
      };

      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      try {
        logger.recordNode('start');

        // Step 1: Improve prompt and ask clarifying questions
        logger.recordNode('improve_prompt');
        state.improvedPrompt = await improvePrompt(state.initialPrompt, state.generatorTags);
        state.traversedNodes.push('improve_prompt');
        log.info('Prompt improved');

        // Step 2: Generator creates initial solution
        logger.recordNode('generator_initial');
        state.generatorResponse = await generateSolution(state.improvedPrompt, state.generatorTags);
        state.traversedNodes.push('generator_initial');
        log.info('Initial solution generated');

        // Adversarial loop
        const generatorResponses: string[] = [];
        const allFindings: string[] = [];
        const allPatches: string[] = [];

        for (let round = 1; round <= state.maxRounds; round++) {
          state.roundNumber = round;
          logger.recordNode(`redteam_round_${round}`);

          // Red team attacks
          const findings = await redTeamAttack(
            state.generatorResponse,
            state.improvedPrompt,
            state.redteamTags
          );
          allFindings.push(findings);
          state.redteamFindings = allFindings;
          state.traversedNodes.push(`redteam_round_${round}`);
          log.info(`Red team round ${round} complete`);

          // Check if findings are minimal (ready for judge)
          if (findings.length < 50 || findings.toLowerCase().includes('no significant issues')) {
            log.info('Red team found minimal issues, proceeding to judge');
            break;
          }

          // Generator patches
          logger.recordNode(`generator_patch_${round}`);
          state.generatorResponse = await patchSolution(
            state.generatorResponse,
            findings,
            state.generatorTags
          );
          generatorResponses.push(state.generatorResponse);
          allPatches.push(state.generatorResponse);
          state.patches = allPatches;
          state.traversedNodes.push(`generator_patch_${round}`);
          log.info(`Patch round ${round} complete`);
        }

        state.generatorResponses = generatorResponses;

        // Step 3: Judge validates
        logger.recordNode('judge');
        state.judgeVerdict = await judgeValidation(
          state.initialPrompt,
          state.improvedPrompt,
          generatorResponses,
          allFindings,
          allPatches,
          state.judgeTags
        );
        state.traversedNodes.push('judge');
        log.info('Judge validation complete');

        state.status = 'complete';
        return await finalizeGraph(state);

      } catch (error) {
        log.error(`Adversarial validation error: ${error}`);
        state.status = 'error';

        const metadata = {
          flowType: state.flowType,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'error',
          error: String(error),
          tags: state.judgeTags,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        return {
          response: `Error: ${error instanceof Error ? error.message : String(error)}`,
          model: state.judgeModel,
          traversedNodes: ['start', 'error'],
          error: String(error),
        };
      }
    },
  };
}

// Export singleton
export const adversarialGraph = createAdversarialGraph();
