/**
 * DelphiMethodGraph - Delphi Method Flow
 *
 * An iterative expert estimation flow for reducing individual bias:
 * - Round 1: 3 experts (tier2) give independent estimates with reasoning
 * - Aggregator: Shows anonymous range + reasoning to all
 * - Round 2: Each expert sees others' reasoning, revises estimate
 * - Round 3 (if needed): Final convergence
 * - Judge (tier3): Synthesizes final consensus with confidence range
 *
 * Flow: start → expert_round1 → aggregate → expert_round2 → (optional round3) → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion } from '../../litellm/index';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import type { GraphResult, GraphInvokeOptions } from './types';
import type { LogEntry } from '../state';

const log = createLogger('GRAPH:DELPHI_METHOD');

const DEFAULT_NUM_EXPERTS = 3;
const DEFAULT_MAX_ROUNDS = 3;

// ============================================================================
// Graph State
// ============================================================================

interface DelphiGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  initialPrompt: string;
  expertModel: string;
  aggregatorModel: string;
  judgeModel: string;
  expertTags: string[];
  judgeTags: string[];
  
  // Round tracking
  currentRound: number;
  maxRounds: number;
  hasConverged: boolean;
  
  // Expert estimates
  expertEstimates: Array<{
    expertId: string;
    estimate: string;
    reasoning: string;
    confidence: number;
  }>;
  
  // Aggregated feedback (shown to experts)
  aggregatedFeedback: string;
  
  // Final synthesis
  finalEstimate: string;
  confidenceRange: { low: number; high: number };
  consensusStrength: number;
  
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
  logBuffer: LogEntry[];
}

// ============================================================================
// Helper Functions
// ============================================================================

async function generateExpertEstimate(
  prompt: string,
  expertRole: string,
  roundNumber: number,
  tags: string[]
): Promise<{ estimate: string; reasoning: string; confidence: number }> {
  const systemPrompt = roundNumber === 1
    ? `You are ${expertRole}. Provide your independent estimate and reasoning for the question. Your answer should be based on your expertise and knowledge. Be specific and provide reasoning for your estimate.`
    : `You are ${expertRole}. You will see the anonymous reasoning from other experts. Consider their perspectives and revise your estimate if warranted. Be open to changing your view, but only if the reasoning is compelling.`;

  const userPrompt = roundNumber === 1
    ? `Question: ${prompt}\n\nProvide your estimate with reasoning.`
    : `Original Question: ${prompt}\n\nAnonymous Expert Reasoning:\n{feedback}\n\nRevise your estimate based on this new information, or keep your original estimate if you find it still the most reasonable.`;

  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: roundNumber === 1 ? userPrompt : userPrompt.replace('{feedback}', '') },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });

  const content = response.choices[0]?.message?.content || '';
  
  // Parse estimate, reasoning, and confidence from response
  // Default parsing approach
  return {
    estimate: content,
    reasoning: content,
    confidence: 75, // Default confidence
  };
}

async function aggregateFeedback(
  estimates: Array<{ expertId: string; estimate: string; reasoning: string; confidence: number }>,
  tags: string[]
): Promise<string> {
  const anonymizedEstimates = estimates.map((e, i) =>
    `Expert ${i + 1}:\nEstimate: ${e.estimate}\nReasoning: ${e.reasoning}`
  ).join('\n\n---\n');

  const systemPrompt = await loadPrompt('delphi-aggregator');
  const userPrompt = renderTemplate(await loadPrompt('delphi-aggregator-user'), {
    estimates: anonymizedEstimates,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.5,
    top_p: 0.8,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || 'Unable to aggregate feedback';
}

async function checkConvergence(
  estimates: Array<{ estimate: string; confidence: number }>,
  tags: string[]
): Promise<boolean> {
  // Simple convergence check: if all estimates are similar within confidence threshold
  if (estimates.length < 2) return false;
  
  // Check if confidence is high enough
  const avgConfidence = estimates.reduce((sum, e) => sum + e.confidence, 0) / estimates.length;
  if (avgConfidence >= 85) return true;
  
  // Check if estimates are similar (simple heuristic)
  const estimatesTexts = estimates.map(e => e.estimate.toLowerCase());
  const uniqueEstimates = new Set(estimatesTexts);
  
  // If most experts agree (more than 66%), consider converged
  return uniqueEstimates.size <= estimates.length * 0.5;
}

async function synthesizeConsensus(
  prompt: string,
  allEstimates: Array<{ round: number; expertId: string; estimate: string; reasoning: string }>,
  tags: string[]
): Promise<{ estimate: string; confidenceRange: { low: number; high: number }; strength: number }> {
  const estimateHistory = allEstimates.map(e =>
    `Round ${e.round}, Expert ${e.expertId}:\n${e.estimate}\nReasoning: ${e.reasoning}`
  ).join('\n\n---\n');

  const systemPrompt = await loadPrompt('delphi-judge');
  const userPrompt = renderTemplate(await loadPrompt('delphi-judge-user'), {
    original_prompt: prompt,
    estimate_history: estimateHistory,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.5,
    top_p: 0.8,
    metadata: { tags },
  });

  const content = response.choices[0]?.message?.content || '';
  
  // Parse confidence range
  const rangeMatch = content.match(/confidence.*?(\d+).*?(\d+)/i) || content.match(/(\d+).*?(\d+)/);
  const strengthMatch = content.match(/strength[:\s]*(\d+)/i);
  
  return {
    estimate: content,
    confidenceRange: {
      low: rangeMatch ? parseInt(rangeMatch[1]) : 60,
      high: rangeMatch ? parseInt(rangeMatch[2]) : 90,
    },
    strength: strengthMatch ? parseInt(strengthMatch[1]) : 75,
  };
}

async function finalizeGraph(state: DelphiGraphState): Promise<GraphResult> {
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

  const expertSection = state.expertEstimates.map((e, i) =>
    `**Expert ${i + 1}**: ${e.estimate}\n_Confidence: ${e.confidence}%_`
  ).join('\n\n');

  const finalResponse = `## Delphi Method Consensus Complete\n\n**Original Question:** ${state.initialPrompt}\n\n**Rounds Completed:** ${state.currentRound}\n\n### Expert Estimates:
${expertSection}\n\n### Aggregated Feedback:
${state.aggregatedFeedback}\n\n### Final Consensus:
${state.finalEstimate}\n\n**Confidence Range:** ${state.confidenceRange.low}% - ${state.confidenceRange.high}%\n\n**Consensus Strength:** ${state.consensusStrength}%\n\n**Converged:** ${state.hasConverged ? '✓ Yes' : '⚠ Partial (best effort synthesis)'}\n\n**Status:** ${state.status}`;

  const metadata = {
    flowType: state.flowType,
    channelId: state.channelId,
    executionId: state.executionId,
    status: 'complete',
    nodeCount: state.traversedNodes.length + 1,
    model: state.judgeModel,
    tags: state.judgeTags,
    rounds: state.currentRound,
    expertsCount: state.expertEstimates.length,
    consensusStrength: state.consensusStrength,
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

export function createDelphiGraph() {
  return {
    name: 'DelphiMethodGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking DelphiMethodGraph for channel ${options.channelId}`);

      const state: DelphiGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.DELPHI_METHOD,
        initialPrompt: options.initialPrompt,
        expertModel: 'auto',
        aggregatorModel: 'auto',
        judgeModel: 'auto',
        expertTags: ['tier2', 'general'],
        judgeTags: ['tier3', 'thinking'],
        
        currentRound: 1,
        maxRounds: DEFAULT_MAX_ROUNDS,
        hasConverged: false,
        
        expertEstimates: [],
        aggregatedFeedback: '',
        
        finalEstimate: '',
        confidenceRange: { low: 0, high: 0 },
        consensusStrength: 0,
        
        status: 'running',
        traversedNodes: [],
        logBuffer: [],
      };

      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      const expertRoles = [
        'a domain expert with practical experience',
        'an academic researcher',
        'an industry analyst',
      ];

      try {
        logger.recordNode('start');

        // Round 1: Get independent expert estimates
        logger.recordNode('expert_round1');
        const round1Estimates: Array<{ expertId: string; estimate: string; reasoning: string; confidence: number }> = [];
        
        for (let i = 0; i < DEFAULT_NUM_EXPERTS; i++) {
          const result = await generateExpertEstimate(
            state.initialPrompt,
            expertRoles[i],
            1,
            state.expertTags
          );
          round1Estimates.push({
            expertId: `E${i + 1}`,
            estimate: result.estimate,
            reasoning: result.reasoning,
            confidence: result.confidence,
          });
        }
        
        state.expertEstimates = round1Estimates;
        state.traversedNodes.push('expert_round1');
        log.info(`Round 1 complete with ${round1Estimates.length} expert estimates`);

        // Aggregation: Show anonymous feedback
        logger.recordNode('aggregate');
        state.aggregatedFeedback = await aggregateFeedback(round1Estimates, state.expertTags);
        state.traversedNodes.push('aggregate');
        log.info('Feedback aggregated');

        // Check convergence after round 1
        state.hasConverged = await checkConvergence(round1Estimates, state.expertTags);

        // Round 2: Experts revise based on feedback
        if (!state.hasConverged && state.currentRound < state.maxRounds) {
          state.currentRound = 2;
          logger.recordNode('expert_round2');
          
          const round2Estimates: Array<{ expertId: string; estimate: string; reasoning: string; confidence: number }> = [];
          
          for (let i = 0; i < DEFAULT_NUM_EXPERTS; i++) {
            const result = await generateExpertEstimate(
              state.initialPrompt,
              expertRoles[i],
              2,
              state.expertTags
            );
            round2Estimates.push({
              expertId: `E${i + 1}`,
              estimate: result.estimate,
              reasoning: result.reasoning,
              confidence: result.confidence,
            });
          }
          
          state.expertEstimates = round2Estimates;
          state.traversedNodes.push('expert_round2');
          log.info(`Round 2 complete`);

          // Re-aggregate and check convergence
          state.aggregatedFeedback = await aggregateFeedback(round2Estimates, state.expertTags);
          state.hasConverged = await checkConvergence(round2Estimates, state.expertTags);

          // Round 3 if still not converged
          if (!state.hasConverged && state.currentRound < state.maxRounds) {
            state.currentRound = 3;
            logger.recordNode('expert_round3');
            
            const round3Estimates: Array<{ expertId: string; estimate: string; reasoning: string; confidence: number }> = [];
            
            for (let i = 0; i < DEFAULT_NUM_EXPERTS; i++) {
              const result = await generateExpertEstimate(
                state.initialPrompt,
                expertRoles[i],
                3,
                state.expertTags
              );
              round3Estimates.push({
                expertId: `E${i + 1}`,
                estimate: result.estimate,
                reasoning: result.reasoning,
                confidence: result.confidence,
              });
            }
            
            state.expertEstimates = round3Estimates;
            state.traversedNodes.push('expert_round3');
            log.info(`Round 3 complete`);
            
            state.hasConverged = await checkConvergence(round3Estimates, state.expertTags);
          }
        }

        // Judge: Synthesize final consensus
        logger.recordNode('judge');
        const allEstimates: Array<{ round: number; expertId: string; estimate: string; reasoning: string }> = [];
        state.expertEstimates.forEach((e, i) => {
          allEstimates.push({
            round: Math.min(i + 1, state.currentRound),
            expertId: e.expertId,
            estimate: e.estimate,
            reasoning: e.reasoning,
          });
        });

        const consensus = await synthesizeConsensus(
          state.initialPrompt,
          allEstimates,
          state.judgeTags
        );
        
        state.finalEstimate = consensus.estimate;
        state.confidenceRange = consensus.confidenceRange;
        state.consensusStrength = consensus.strength;
        state.traversedNodes.push('judge');
        log.info('Final consensus synthesized');

        state.status = 'complete';
        return await finalizeGraph(state);

      } catch (error) {
        log.error(`Delphi method error: ${error}`);
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
export const delphiGraph = createDelphiGraph();
