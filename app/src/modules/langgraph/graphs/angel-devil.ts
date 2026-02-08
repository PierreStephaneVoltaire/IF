/**
 * AngelDevilGraph - Enhanced with Steel Manning
 *
 * A parallel graph for moral/ethical debate with steel-manning enhancement.
 * Flow:
 * 1. Angel argues FOR (tier2)
 * 2. Devil argues AGAINST (tier2) — parallel with step 1
 * 3. Angel steel-mans Devil: "What's the STRONGEST version of their argument?"
 * 4. Devil steel-mans Angel: "What's the STRONGEST version of their argument?" — parallel with step 3
 * 5. Angel responds to strengthened Devil argument
 * 6. Devil responds to strengthened Angel argument — parallel with step 5
 * 7. Judge (tier3 + thinking): Synthesizes with both strongest arguments
 *
 * Flow: start → angel → devil → angel_steelman → devil_steelman → angel_respond → devil_respond → judge → finalize
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
  
  // Round 1: Initial arguments
  angelArgument: string;
  devilArgument: string;
  
  // Round 2: Steel-manning
  angelSteelmansDevil: string;  // Angel improves Devil's argument
  devilSteelMansAngel: string; // Devil improves Angel's argument
  
  // Round 3: Responses to strengthened arguments
  angelRespondsToStrengthenedDevil: string;
  devilRespondsToStrengthenedAngel: string;
  
  // Final synthesis
  synthesis: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Helper Functions
// ============================================================================

async function generateAngelArgument(question: string, tags: string[]): Promise<string> {
  const angelPrompt = renderTemplate(loadPrompt('angel-devil-angel'), {
    user_question: question,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [{ role: 'user', content: angelPrompt }],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });
  
  return extractContent(response);
}

async function generateDevilArgument(question: string, tags: string[]): Promise<string> {
  const devilPrompt = renderTemplate(loadPrompt('angel-devil-devil'), {
    user_question: question,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [{ role: 'user', content: devilPrompt }],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });
  
  return extractContent(response);
}

async function steelmanOpposingArgument(
  ownArgument: string,
  opposingArgument: string,
  question: string,
  role: 'angel' | 'devil',
  tags: string[]
): Promise<string> {
  const roleName = role === 'angel' ? 'Angel' : 'Devil';
  const opposingRole = role === 'angel' ? 'Devil' : 'Angel';

  const systemPrompt = renderTemplate(loadPrompt('angel-devil-steelman'), {
    role: roleName,
    opposing_role: opposingRole,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      {
        role: 'user',
        content: `Question: ${question}\n\nYour original argument:\n${ownArgument}\n\n${opposingRole}'s original argument:\n${opposingArgument}\n\nSteel-man the ${opposingRole}'s argument: What is the STRONGEST version of their position?`
      },
    ],
    temperature: 0.8,
    top_p: 0.95,
    metadata: { tags },
  });
  
  return extractContent(response);
}

async function respondToStrengthenedArgument(
  ownOriginal: string,
  strengthenedOpposing: string,
  question: string,
  role: 'angel' | 'devil',
  tags: string[]
): Promise<string> {
  const roleName = role === 'angel' ? 'Angel' : 'Devil';
  const opposingRole = role === 'angel' ? 'Devil' : 'Angel';

  const systemPrompt = renderTemplate(loadPrompt('angel-devil-respond'), {
    role: roleName,
    opposing_role: opposingRole,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      {
        role: 'user',
        content: `Question: ${question}\n\nYour original argument:\n${ownOriginal}\n\n${opposingRole}'s STEEL-MANNED argument (their strongest case):\n${strengthenedOpposing}\n\nRespond to their strongest argument:`
      },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });
  
  return extractContent(response);
}

async function generateSynthesis(
  question: string,
  angelOriginal: string,
  devilOriginal: string,
  angelSteelman: string,
  devilSteelman: string,
  angelResponse: string,
  devilResponse: string,
  tags: string[]
): Promise<string> {
  const judgePrompt = renderTemplate(loadPrompt('angel-devil-judge'), {
    user_question: question,
    angel_argument: angelOriginal,
    devil_argument: devilOriginal,
  });

  const enhancedJudgePrompt = `${judgePrompt}\n\n=== ENHANCED ANALYSIS WITH STEEL-MANNING ===

**Angel's Original Position:** ${angelOriginal}

**Devil's Original Position:** ${devilOriginal}

**Angel's Steel-Man of Devil:** (How Angel improves Devil's argument)
${angelSteelman}

**Devil's Steel-Man of Angel:** (How Devil improves Angel's argument)
${devilSteelman}

**Angel's Response to Steel-Manned Devil:**
${angelResponse}

**Devil's Response to Steel-Manned Angel:**
${devilResponse}

=== SYNTHESIS REQUIREMENTS ===
Based on this enhanced debate with steel-manning:
1. Identify the strongest points from each side (now both original AND steel-manned versions)
2. Show how each side's position evolved through the steel-manning process
3. Provide a balanced synthesis that acknowledges the valid points from BOTH perspectives
4. Present a nuanced final conclusion that represents genuine辩证思维 (dialectical thinking)
`;

  const response = await chatCompletion({
    model: 'auto',
    messages: [{ role: 'user', content: enhancedJudgePrompt }],
    temperature: 0.6,
    top_p: 0.85,
    metadata: { tags },
  });
  
  return extractContent(response);
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createAngelDevilGraph() {
  return {
    name: 'AngelDevilGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking Enhanced AngelDevilGraph for channel ${options.channelId}`);

      const debateTags = ['tier2', 'general'];
      const judgeTags = ['tier3', 'thinking'];

      const params = getModelParams(FlowType.ANGEL_DEVIL);
      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      const state: AngelDevilGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.ANGEL_DEVIL,
        userQuestion: options.initialPrompt,
        debateTags,
        judgeTags,
        angelModel: 'auto',
        devilModel: 'auto',
        judgeModel: 'auto',
        angelArgument: '',
        devilArgument: '',
        angelSteelmansDevil: '',
        devilSteelMansAngel: '',
        angelRespondsToStrengthenedDevil: '',
        devilRespondsToStrengthenedAngel: '',
        synthesis: '',
        status: 'running',
        traversedNodes: [],
      };

      try {
        logger.recordNode('start');

        // === ROUND 1: Initial Arguments (Parallel) ===
        logger.recordNode('angel_round1');
        logger.recordNode('devil_round1');
        
        state.traversedNodes.push('angel_round1', 'devil_round1');
        
        const [angelArgument, devilArgument] = await Promise.all([
          generateAngelArgument(options.initialPrompt, debateTags),
          generateDevilArgument(options.initialPrompt, debateTags),
        ]);
        
        state.angelArgument = angelArgument;
        state.devilArgument = devilArgument;
        
        log.info(`Round 1: Angel (${angelArgument.length} chars), Devil (${devilArgument.length} chars)`);

        // === ROUND 2: Steel-Manning (Parallel) ===
        logger.recordNode('angel_steelman');
        logger.recordNode('devil_steelman');
        
        state.traversedNodes.push('angel_steelman', 'devil_steelman');
        
        const [angelSteelman, devilSteelman] = await Promise.all([
          steelmanOpposingArgument(
            state.angelArgument,
            state.devilArgument,
            options.initialPrompt,
            'angel',
            debateTags
          ),
          steelmanOpposingArgument(
            state.devilArgument,
            state.angelArgument,
            options.initialPrompt,
            'devil',
            debateTags
          ),
        ]);
        
        state.angelSteelmansDevil = angelSteelman;
        state.devilSteelMansAngel = devilSteelman;
        
        log.info(`Round 2: Steel-manning complete`);

        // === ROUND 3: Responses to Strengthened Arguments (Parallel) ===
        logger.recordNode('angel_respond');
        logger.recordNode('devil_respond');
        
        state.traversedNodes.push('angel_respond', 'devil_respond');
        
        const [angelResponse, devilResponse] = await Promise.all([
          respondToStrengthenedArgument(
            state.angelArgument,
            state.devilSteelMansAngel,
            options.initialPrompt,
            'angel',
            debateTags
          ),
          respondToStrengthenedArgument(
            state.devilArgument,
            state.angelSteelmansDevil,
            options.initialPrompt,
            'devil',
            debateTags
          ),
        ]);
        
        state.angelRespondsToStrengthenedDevil = angelResponse;
        state.devilRespondsToStrengthenedAngel = devilResponse;
        
        log.info(`Round 3: Responses to strengthened arguments complete`);

        // === FINAL: Judge Synthesis ===
        logger.recordNode('judge');
        state.traversedNodes.push('judge');
        
        state.synthesis = await generateSynthesis(
          options.initialPrompt,
          state.angelArgument,
          state.devilArgument,
          state.angelSteelmansDevil,
          state.devilSteelMansAngel,
          state.angelRespondsToStrengthenedDevil,
          state.devilRespondsToStrengthenedAngel,
          judgeTags
        );
        
        log.info(`Final synthesis: ${state.synthesis.length} chars`);

        logger.recordNode('finalize');
        state.traversedNodes.push('finalize');

        const generator = getMermaidGenerator();
        const mermaidSource = generator.generate({
          flowType: FlowType.ANGEL_DEVIL,
          traversedNodes: state.traversedNodes,
          turns: [],
          finalStatus: 'complete',
        });

        await logger.uploadMermaid(mermaidSource);
        const mermaidPng = await generator.renderPng(mermaidSource);
        await logger.uploadDiagramPng(mermaidPng);

        const finalResponse = `## Angel/Devil Debate with Steel Manning Complete

**Question:** ${options.initialPrompt}

### Round 1: Initial Arguments

**👼 Angel's Argument (FOR):**
${state.angelArgument}

**😈 Devil's Argument (AGAINST):**
${state.devilArgument}

### Round 2: Steel-Manning
*Each side strengthens the other's argument*

**👼 Angel's Steel-Man of Devil:**
${state.angelSteelmansDevil}

**😈 Devil's Steel-Man of Angel:**
${state.devilSteelMansAngel}

### Round 3: Responses to Strengthened Arguments

**👼 Angel's Response to Steel-Manned Devil:**
${state.angelRespondsToStrengthenedDevil}

**😈 Devil's Response to Steel-Manned Angel:**
${state.devilRespondsToStrengthenedAngel}

### Final Synthesis
${state.synthesis}

---

*This analysis used steel-manning to ensure both perspectives were presented in their strongest possible form before synthesis.*`;

        const metadata = {
          flowType: FlowType.ANGEL_DEVIL,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'complete',
          nodeCount: state.traversedNodes.length,
          tags: judgeTags,
          rounds: 3,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        return {
          response: finalResponse,
          model: 'auto',
          traversedNodes: state.traversedNodes,
        };

      } catch (error) {
        log.error(`Angel/Devil error: ${error}`);
        state.status = 'error';

        const metadata = {
          flowType: FlowType.ANGEL_DEVIL,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'error',
          error: String(error),
          tags: judgeTags,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        return {
          response: `Error: ${error instanceof Error ? error.message : String(error)}`,
          model: 'auto',
          traversedNodes: ['start', 'error'],
          error: String(error),
        };
      }
    },
  };
}

// Export singleton
export const angelDevilGraph = createAngelDevilGraph();
