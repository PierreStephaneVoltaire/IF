/**
 * AngelDevilGraph - Multi-Node Flow
 *
 * Implements angel/devil debate pattern for moral/ethical decisions.
 * Uses model group-based routing:
 * - Angel/Devil arguments: general-tier2
 * - Steelman: general-tier3-thinking
 * - Judge: general-tier3
 *
 * Flow: start → angel → devil → steelman → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, tagsToModelGroup } from '../../litellm/index';
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
  question: string;
  angelModelGroup: string;
  devilModelGroup: string;
  steelmanModelGroup: string;
  judgeModelGroup: string;
  angelModel: string;
  devilModel: string;
  steelmanModel: string;
  judgeModel: string;
  angelResponse: string;
  devilResponse: string;
  steelman: string;
  finalResponse: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Generate angel's argument (supporting the decision)
 */
async function angelNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  log.info(`AngelDevilGraph: Angel argument for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-angel'), {
      question: state.question,
    });

    const response = await chatCompletion({
      model: state.angelModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      angelResponse: extractContent(response),
      angelModel: response.model,
      traversedNodes: ['start', 'angel'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      finalResponse: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Generate devil's argument (opposing the decision)
 */
async function devilNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  log.info(`AngelDevilGraph: Devil argument for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-devil'), {
      question: state.question,
    });

    const response = await chatCompletion({
      model: state.devilModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      devilResponse: extractContent(response),
      devilModel: response.model,
      traversedNodes: [...state.traversedNodes, 'devil'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      finalResponse: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Generate steelman (strongest counter-argument)
 */
async function steelmanNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  log.info(`AngelDevilGraph: Steelman for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-steelman'), {
      question: state.question,
      angel_response: state.angelResponse,
      devil_response: state.devilResponse,
    });

    const response = await chatCompletion({
      model: state.steelmanModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      steelman: extractContent(response),
      steelmanModel: response.model,
      traversedNodes: [...state.traversedNodes, 'steelman'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      finalResponse: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Judge node - provides final balanced response
 */
async function judgeNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('judge');

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-respond'), {
      question: state.question,
      angel_response: state.angelResponse,
      devil_response: state.devilResponse,
      steelman: state.steelman,
    });

    const response = await chatCompletion({
      model: state.judgeModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    const judgeModel = response.model;

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'angel', 'devil', 'steelman', 'judge'],
      turns: [],
      finalStatus: 'complete',
    });

    await logger.uploadMermaid(mermaidSource);
    const mermaidPng = await generator.renderPng(mermaidSource);
    await logger.uploadDiagramPng(mermaidPng);

    // Upload metadata
    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'complete',
      nodeCount: 5,
      angelModel: state.angelModel,
      devilModel: state.devilModel,
      steelmanModel: state.steelmanModel,
      judgeModel,
      modelGroup: state.judgeModelGroup,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      finalResponse: content,
      judgeModel,
      status: 'complete',
      traversedNodes: [...state.traversedNodes, 'judge'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      finalResponse: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createAngelDevilGraph() {
  return {
    name: 'AngelDevilGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking AngelDevilGraph for channel ${options.channelId}`);

      // Get model groups from options, or convert tags if provided
      let angelModelGroup = options.modelGroup;
      if (!angelModelGroup && options.tags && options.tags.length > 0) {
        angelModelGroup = tagsToModelGroup(options.tags);
      }
      if (!angelModelGroup) {
        angelModelGroup = 'general-tier2';
      }

      const initialState: AngelDevilGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.ANGEL_DEVIL,
        question: options.initialPrompt,
        angelModelGroup,
        devilModelGroup: angelModelGroup,
        steelmanModelGroup: 'general-tier3-thinking',
        judgeModelGroup: 'general-tier3',
        angelModel: '',
        devilModel: '',
        steelmanModel: '',
        judgeModel: '',
        angelResponse: '',
        devilResponse: '',
        steelman: '',
        finalResponse: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      // Execute flow: angel → devil → steelman → judge
      let state = await angelNode(initialState);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.angelModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await devilNode(state);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.devilModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await steelmanNode(state);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.steelmanModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await judgeNode(state);

      return {
        response: state.finalResponse,
        model: state.judgeModel || state.steelmanModel || state.devilModel || state.angelModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.finalResponse : undefined,
      };
    },
  };
}

// Export singleton
export const angelDevilGraph = createAngelDevilGraph();
