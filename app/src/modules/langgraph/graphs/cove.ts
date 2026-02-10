/**
 * CoveGraph - Multi-Node Flow
 *
 * Implements Chain of Verification for factual accuracy.
 * Uses model group-based routing:
 * - Baseline/Verifier: general-tier2
 * - Reviser: general-tier3
 *
 * Flow: start → baseline → generate_questions → verify_claims → revise → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, tagsToModelGroup } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:COVE');

// ============================================================================
// Graph State
// ============================================================================

interface CoveGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  prompt: string;
  baselineModelGroup: string;
  verifierModelGroup: string;
  reviserModelGroup: string;
  baselineModel: string;
  verifierModel: string;
  reviserModel: string;
  baseline: string;
  verificationQuestions: Array<{ question: string; claim: string }>;
  verificationResults: Array<{ question: string; isAccurate: boolean; explanation: string }>;
  revised: string;
  contradictions: boolean;
  confidence: number;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Generate baseline response
 */
async function baselineNode(state: CoveGraphState): Promise<CoveGraphState> {
  log.info(`CoveGraph: Baseline generation for channel ${state.channelId}`);

  try {
    const systemPrompt = loadPrompt('cove-baseline');
    const params = getModelParams(FlowType.CHAIN_OF_VERIFICATION);

    const response = await chatCompletion({
      model: state.baselineModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: state.prompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const baseline = extractContent(response);
    const baselineModel = response.model;

    return {
      ...state,
      baseline,
      baselineModel,
      traversedNodes: ['start', 'baseline'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      revised: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Generate verification questions
 */
async function generateQuestionsNode(state: CoveGraphState): Promise<CoveGraphState> {
  try {
    const params = getModelParams(FlowType.CHAIN_OF_VERIFICATION);
    const prompt = renderTemplate(loadPrompt('cove-verify-claim-user'), {
      claim: state.baseline,
    });

    const response = await chatCompletion({
      model: state.verifierModelGroup,
      messages: [
        { role: 'system', content: loadPrompt('cove-verify-claim') },
        { role: 'user', content: prompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    // Parse questions from response (simplified)
    const questions = content.split('\n').filter(l => l.trim().length > 0).map(q => ({
      question: q.replace(/^\d+\.\s*/, ''),
      claim: state.baseline,
    }));

    return {
      ...state,
      verificationQuestions: questions,
      verifierModel: response.model,
      traversedNodes: [...state.traversedNodes, 'generate_questions'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      revised: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Verify claims
 */
async function verifyClaimsNode(state: CoveGraphState): Promise<CoveGraphState> {
  try {
    const params = getModelParams(FlowType.CHAIN_OF_VERIFICATION);

    const results = await Promise.all(
      state.verificationQuestions.map(async (q) => {
        const response = await chatCompletion({
          model: state.verifierModelGroup,
          messages: [
            { role: 'user', content: `Claim: ${q.claim}\n\nQuestion: ${q.question}` },
          ],
          temperature: params.temperature,
          top_p: params.top_p,
        });

        const content = extractContent(response);
        const isAccurate = content.toLowerCase().includes('yes') || content.toLowerCase().includes('accurate');

        return { ...q, isAccurate, explanation: content };
      })
    );

    return {
      ...state,
      verificationResults: results,
      traversedNodes: [...state.traversedNodes, 'verify_claims'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      revised: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Revise response based on verification
 */
async function reviseNode(state: CoveGraphState): Promise<CoveGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('revise');

  try {
    const systemPrompt = loadPrompt('cove-revision-judge');
    const params = getModelParams(FlowType.CHAIN_OF_VERIFICATION);

    const verificationText = state.verificationResults
      .map((r, i) => `Q${i + 1}: ${r.question}\n   Accurate: ${r.isAccurate ? 'Yes' : 'No'}\n   ${r.explanation}`)
      .join('\n');

    const response = await chatCompletion({
      model: state.reviserModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        {
          role: 'user',
          content: `Original: ${state.baseline}\n\nVerification Results:\n${verificationText}`,
        },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    const reviserModel = response.model;

    // Parse for contradictions and confidence
    const hasContradictions = content.toLowerCase().includes('contradiction') ||
                              state.verificationResults.some(r => !r.isAccurate);
    const confidenceMatch = content.match(/confidence[:\s]*(\d+)/i);
    const confidence = confidenceMatch ? parseInt(confidenceMatch[1], 10) : 
                       state.verificationResults.filter(r => r.isAccurate).length / 
                       Math.max(state.verificationResults.length, 1) * 100;

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'baseline', 'generate_questions', 'verify_claims', 'revise'],
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
      baselineModel: state.baselineModel,
      verifierModel: state.verifierModel,
      reviserModel,
      contradictions: hasContradictions,
      confidence: Math.round(confidence),
      modelGroup: state.reviserModelGroup,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      revised: content,
      reviserModel,
      contradictions: hasContradictions,
      confidence: Math.round(confidence),
      status: 'complete',
      traversedNodes: [...state.traversedNodes, 'revise'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      revised: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createCoveGraph() {
  return {
    name: 'CoveGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking CoveGraph for channel ${options.channelId}`);

      // Get model groups from options, or convert tags if provided
      let baselineModelGroup = options.modelGroup;
      if (!baselineModelGroup && options.tags && options.tags.length > 0) {
        baselineModelGroup = tagsToModelGroup(options.tags);
      }
      if (!baselineModelGroup) {
        baselineModelGroup = 'general-tier2';
      }

      const initialState: CoveGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.CHAIN_OF_VERIFICATION,
        prompt: options.initialPrompt,
        baselineModelGroup,
        verifierModelGroup: baselineModelGroup,
        reviserModelGroup: 'general-tier3',
        baselineModel: '',
        verifierModel: '',
        reviserModel: '',
        baseline: '',
        verificationQuestions: [],
        verificationResults: [],
        revised: '',
        contradictions: false,
        confidence: 0,
        status: 'running',
        traversedNodes: ['start'],
      };

      // Execute flow: baseline → questions → verify → revise
      let state = await baselineNode(initialState);
      if (state.status === 'error') {
        return { response: state.revised, model: state.baselineModel, traversedNodes: state.traversedNodes, error: state.revised };
      }

      state = await generateQuestionsNode(state);
      state = await verifyClaimsNode(state);
      state = await reviseNode(state);

      return {
        response: state.revised,
        model: state.reviserModel || state.baselineModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.revised : undefined,
      };
    },
  };
}

// Export singleton
export const coveGraph = createCoveGraph();

// Alias for backward compatibility
export const createChainOfVerificationGraph = createCoveGraph;
