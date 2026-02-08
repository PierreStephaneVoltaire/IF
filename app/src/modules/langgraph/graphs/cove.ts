/**
 * ChainOfVerificationGraph - CoVe Flow
 *
 * A verification-focused flow for factual questions with high hallucination risk.
 * Uses a baseline/verification/revise pattern:
 * - Baseline (tier2): Generate initial answer
 * - Same model: Generate verification questions about the answer
 * - Same model: Answer each verification question independently (baseline NOT visible)
 * - Reviser (tier3): Compare baseline vs verification answers
 *   - Contradictions → revise answer
 *   - Aligned → confidence boost
 *
 * Flow: start → baseline → generate_verifications → verify_claims → revise → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion } from '../../litellm/index';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import type { GraphResult, GraphInvokeOptions } from './types';
import type { LogEntry } from '../state';

const log = createLogger('GRAPH:CHAIN_OF_VERIFICATION');

const DEFAULT_MAX_CLAIMS = 5;

// ============================================================================
// Graph State
// ============================================================================

interface VerificationQuestion {
  question: string;
  claim: string;
}

interface CoveGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  initialPrompt: string;
  baselineTags: string[];
  verifierTags: string[];
  reviserTags: string[];
  baselineModel: string;
  verifierModel: string;
  reviserModel: string;
  baselineResponse: string;
  verificationQuestions: VerificationQuestion[];
  verificationAnswers: string[];
  revisedResponse: string;
  contradictionsFound: boolean;
  confidenceScore: number;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
  logBuffer: LogEntry[];
}

// ============================================================================
// Helper Functions
// ============================================================================

async function generateBaseline(prompt: string, tags: string[]): Promise<string> {
  const systemPrompt = await loadPrompt('cove-baseline');
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: prompt },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || 'No answer generated';
}

async function generateVerificationQuestions(
  baseline: string,
  prompt: string,
  tags: string[]
): Promise<VerificationQuestion[]> {
  const systemPrompt = renderTemplate(await loadPrompt('cove-verification-generator'), {
    max_claims: String(DEFAULT_MAX_CLAIMS),
  });
  
  const userPrompt = renderTemplate(await loadPrompt('cove-verification-user'), {
    original_prompt: prompt,
    baseline: baseline,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.5,
    top_p: 0.85,
    metadata: { tags },
  });

  const content = response.choices[0]?.message?.content || '[]';
  
  try {
    // Try to parse JSON from the response
    const jsonMatch = content.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
    return [];
  } catch {
    return [];
  }
}

async function verifyClaim(
  question: string,
  prompt: string,
  tags: string[]
): Promise<string> {
  // IMPORTANT: Baseline is NOT visible to the verifier
  const systemPrompt = await loadPrompt('cove-verify-claim');
  const userPrompt = renderTemplate(await loadPrompt('cove-verify-claim-user'), {
    original_prompt: prompt,
    verification_question: question,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.3,  // Lower temperature for factual consistency
    top_p: 0.8,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || 'Unable to verify';
}

async function compareAndRevise(
  originalPrompt: string,
  baseline: string,
  verifications: VerificationQuestion[],
  answers: string[],
  tags: string[]
): Promise<{ revised: string; contradictions: boolean; confidence: number }> {
  const verificationText = verifications.map((v, i) =>
    `Question: ${v.question}\nOriginal Claim: ${v.claim}\nVerification Answer: ${answers[i]}`
  ).join('\n\n---\n');

  const systemPrompt = await loadPrompt('cove-revision-judge');
  const userPrompt = renderTemplate(await loadPrompt('cove-revision-user'), {
    original_prompt: originalPrompt,
    baseline: baseline,
    verification_results: verificationText,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.5,
    top_p: 0.85,
    metadata: { tags },
  });

  const content = response.choices[0]?.message?.content || '';
  
  try {
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const result = JSON.parse(jsonMatch[0]);
      return {
        revised: result.revised_answer || content,
        contradictions: result.contradictions_found || false,
        confidence: result.confidence_score || 70,
      };
    }
    return { revised: content, contradictions: false, confidence: 70 };
  } catch {
    return { revised: content, contradictions: false, confidence: 70 };
  }
}

async function finalizeGraph(state: CoveGraphState): Promise<GraphResult> {
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

  const verificationSection = state.verificationQuestions.map((q, i) =>
    `**Verification ${i + 1}:** ${q.question}\n**Original Claim:** ${q.claim}\n**Answer:** ${state.verificationAnswers[i] || 'N/A'}`
  ).join('\n\n');

  const finalResponse = `## Chain of Verification Complete\n\n**Original Question:** ${state.initialPrompt}\n\n### Baseline Answer:\n${state.baselineResponse}\n\n### Verification Process:\n${verificationSection}\n\n### Final Answer:\n${state.contradictionsFound ? '_(Answer revised based on verification findings)_\n' : '_(Answer verified - high confidence)_\n'}${state.revisedResponse || state.baselineResponse}\n\n**Verification Confidence:** ${state.confidenceScore}%\n\n**Status:** ${state.status}`;

  const metadata = {
    flowType: state.flowType,
    channelId: state.channelId,
    executionId: state.executionId,
    status: 'complete',
    nodeCount: state.traversedNodes.length + 1,
    model: state.reviserModel,
    tags: state.reviserTags,
    confidence: state.confidenceScore,
    contradictionsFound: state.contradictionsFound,
    timestamp: new Date().toISOString(),
  };

  await logger.uploadMetadata(metadata);
  await logger.flush();

  return {
    response: finalResponse,
    model: state.reviserModel,
    traversedNodes: state.traversedNodes,
  };
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createChainOfVerificationGraph() {
  return {
    name: 'ChainOfVerificationGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking ChainOfVerificationGraph for channel ${options.channelId}`);

      const state: CoveGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.CHAIN_OF_VERIFICATION,
        initialPrompt: options.initialPrompt,
        baselineTags: ['tier2', 'general'],
        verifierTags: ['tier2', 'general'],
        reviserTags: ['tier3', 'thinking'],
        baselineModel: 'auto',
        verifierModel: 'auto',
        reviserModel: 'auto',
        baselineResponse: '',
        verificationQuestions: [],
        verificationAnswers: [],
        revisedResponse: '',
        contradictionsFound: false,
        confidenceScore: 0,
        status: 'running',
        traversedNodes: [],
        logBuffer: [],
      };

      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      try {
        logger.recordNode('start');

        // Step 1: Generate baseline answer
        logger.recordNode('baseline');
        state.baselineResponse = await generateBaseline(state.initialPrompt, state.baselineTags);
        state.traversedNodes.push('baseline');
        log.info('Baseline answer generated');

        // Step 2: Generate verification questions
        logger.recordNode('generate_verifications');
        state.verificationQuestions = await generateVerificationQuestions(
          state.baselineResponse,
          state.initialPrompt,
          state.verifierTags
        );
        state.traversedNodes.push('generate_verifications');
        log.info(`Generated ${state.verificationQuestions.length} verification questions`);

        // Step 3: Verify each claim independently
        const verificationAnswers: string[] = [];
        for (let i = 0; i < state.verificationQuestions.length; i++) {
          const vq = state.verificationQuestions[i];
          logger.recordNode(`verify_claim_${i + 1}`);
          
          const answer = await verifyClaim(vq.question, state.initialPrompt, state.verifierTags);
          verificationAnswers.push(answer);
          state.traversedNodes.push(`verify_claim_${i + 1}`);
          log.info(`Verification ${i + 1} complete`);
        }
        state.verificationAnswers = verificationAnswers;

        // Step 4: Compare and revise
        logger.recordNode('revise');
        const revisionResult = await compareAndRevise(
          state.initialPrompt,
          state.baselineResponse,
          state.verificationQuestions,
          verificationAnswers,
          state.reviserTags
        );

        state.revisedResponse = revisionResult.revised;
        state.contradictionsFound = revisionResult.contradictions;
        state.confidenceScore = revisionResult.confidence;
        state.traversedNodes.push('revise');
        log.info(`Revision complete. Contradictions: ${state.contradictionsFound}, Confidence: ${state.confidenceScore}%`);

        state.status = 'complete';
        return await finalizeGraph(state);

      } catch (error) {
        log.error(`Chain of verification error: ${error}`);
        state.status = 'error';

        const metadata = {
          flowType: state.flowType,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'error',
          error: String(error),
          tags: state.reviserTags,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        return {
          response: `Error: ${error instanceof Error ? error.message : String(error)}`,
          model: state.reviserModel,
          traversedNodes: ['start', 'error'],
          error: String(error),
        };
      }
    },
  };
}

// Export singleton
export const coveGraph = createChainOfVerificationGraph();
