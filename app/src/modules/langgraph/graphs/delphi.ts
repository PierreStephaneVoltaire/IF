/**
 * DelphiGraph - Multi-Node Flow
 *
 * Implements Delphi method for expert consensus building.
 * Uses model group-based routing:
 * - Experts: delphi-method-tier2
 * - Judge: delphi-method-tier3
 *
 * Flow: start → expert_1 → ... → expert_n → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, tagsToModelGroup } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:DELPHI');

// ============================================================================
// Graph State
// ============================================================================

interface DelphiGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  expertModelGroup: string;
  judgeModelGroup: string;
  expertModels: string[];
  judgeModel: string;
  estimates: Array<{ expertId: string; estimate: string; reasoning: string; confidence: number; model: string }>;
  consensus: { estimate: string; confidenceRange: { low: number; high: number }; strength: number };
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Generate estimates from multiple expert models
 */
async function expertNode(
  state: DelphiGraphState,
  prompt: string,
  expertId: string,
  expertModelGroup: string
): Promise<{ estimate: string; reasoning: string; confidence: number; model: string }> {
  const systemPrompt = loadPrompt('delphi-judge');
  const params = getModelParams(FlowType.DELPHI_METHOD);

  const response = await chatCompletion({
    model: expertModelGroup,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: prompt },
    ],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const content = extractContent(response);
  const model = response.model;

  // Parse response for estimate, reasoning, confidence
  const estimateMatch = content.match(/estimate[:\s]*([\d.]+)/i);
  const reasoningMatch = content.match(/reasoning[:\s]*([\s\S]*)/i);
  const confidenceMatch = content.match(/confidence[:\s]*(\d+)/i);

  return {
    estimate: estimateMatch ? estimateMatch[1] : 'unknown',
    reasoning: reasoningMatch ? reasoningMatch[1].trim() : content,
    confidence: confidenceMatch ? parseInt(confidenceMatch[1], 10) : 50,
    model,
  };
}

/**
 * Judge node - synthesizes expert estimates into consensus
 */
async function judgeNode(state: DelphiGraphState): Promise<DelphiGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('judge');

  try {
    const systemPrompt = loadPrompt('delphi-aggregator');
    const params = getModelParams(FlowType.DELPHI_METHOD);

    const estimatesText = state.estimates
      .map((e, i) => `Expert ${i + 1} (${e.model}): ${e.estimate} - ${e.reasoning}`)
      .join('\n\n');

    const response = await chatCompletion({
      model: state.judgeModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        {
          role: 'user',
          content: `${state.userQuestion}\n\nEstimates:\n${estimatesText}`,
        },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    const judgeModel = response.model;

    // Parse consensus response
    const estimateMatch = content.match(/consensus[:\s]*([\s\S]*)/i);
    const rangeMatch = content.match(/range[:\s]*(\d+)[\s-]*(\d+)/i);
    const strengthMatch = content.match(/strength[:\s]*(\d+)/i);

    const consensus = {
      estimate: estimateMatch ? estimateMatch[1].trim() : content,
      confidenceRange: {
        low: rangeMatch ? parseInt(rangeMatch[1], 10) : 0,
        high: rangeMatch ? parseInt(rangeMatch[2], 10) : 100,
      },
      strength: strengthMatch ? parseInt(strengthMatch[1], 10) : 50,
    };

    log.info(`Delphi consensus: ${consensus.estimate} [${consensus.confidenceRange.low}-${consensus.confidenceRange.high}]`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', ...state.expertModels.map((_, i) => `expert_${i + 1}`), 'judge'],
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
      nodeCount: state.expertModels.length + 1,
      judgeModel,
      expertModels: state.expertModels,
      modelGroup: state.judgeModelGroup,
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
    log.error(`Delphi judge error: ${error}`);
    return {
      ...state,
      status: 'error',
      consensus: {
        estimate: `Error: ${error instanceof Error ? error.message : String(error)}`,
        confidenceRange: { low: 0, high: 100 },
        strength: 0,
      },
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createDelphiGraph() {
  return {
    name: 'DelphiGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking DelphiGraph for channel ${options.channelId}`);

      // Get model groups from options, or convert tags if provided
      let expertModelGroup = options.modelGroup;
      if (!expertModelGroup && options.tags && options.tags.length > 0) {
        expertModelGroup = tagsToModelGroup(options.tags);
      }
      if (!expertModelGroup) {
        expertModelGroup = 'delphi-method-tier2';
      }

      const initialState: DelphiGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.DELPHI_METHOD,
        userQuestion: options.initialPrompt,
        expertModelGroup,
        judgeModelGroup: 'delphi-method-tier3',
        expertModels: [],
        judgeModel: '',
        estimates: [],
        consensus: { estimate: '', confidenceRange: { low: 0, high: 0 }, strength: 0 },
        status: 'running',
        traversedNodes: ['start'],
      };

      // Generate estimates from 3 expert models in parallel
      const expertPrompts = Array(3).fill(null).map((_, i) => 
        renderTemplate(loadPrompt('delphi-judge-user'), {
          round_number: '1',
          expert_id: String(i + 1),
          question: options.initialPrompt,
          previous_estimates: '',
        })
      );

      const expertResults = await Promise.all(
        expertPrompts.map((prompt, i) => 
          expertNode(initialState, prompt, String(i + 1), expertModelGroup)
        )
      );

      const estimates = expertResults.map((r, i) => ({
        expertId: String(i + 1),
        estimate: r.estimate,
        reasoning: r.reasoning,
        confidence: r.confidence,
        model: r.model,
      }));

      const stateAfterExperts = {
        ...initialState,
        estimates,
        expertModels: expertResults.map(r => r.model),
        traversedNodes: ['start', ...expertResults.map((_, i) => `expert_${i + 1}`)],
      };

      // Execute judge node
      const finalState = await judgeNode(stateAfterExperts);

      return {
        response: `${finalState.consensus.estimate}\n\nConfidence Range: ${finalState.consensus.confidenceRange.low}-${finalState.consensus.confidenceRange.high}\nStrength: ${finalState.consensus.strength}%`,
        model: finalState.judgeModel || finalState.expertModels[0] || 'delphi-method-tier2',
        traversedNodes: finalState.traversedNodes,
        error: finalState.status === 'error' ? finalState.consensus.estimate : undefined,
      };
    },
  };
}

// Export singleton
export const delphiGraph = createDelphiGraph();
