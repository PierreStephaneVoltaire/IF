/**
 * AngelDevilGraph - Multi-Node Flow
 *
 * Implements angel/devil debate pattern for moral/ethical decisions.
 * Uses model group-based routing:
 * - Angel/Devil arguments: angel-devil-tier2
 * - Steelman + Responses: angel-devil-tier3
 * - Judge: angel-devil-tier3
 *
 * Flow: start → angel → devil → angel_steelman → devil_steelman → angel_respond → devil_respond → judge → finalize
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
  angelSteelmanModel: string;
  devilSteelmanModel: string;
  angelRespondModel: string;
  devilRespondModel: string;
  judgeModel: string;
  angelResponse: string;
  devilResponse: string;
  angelSteelman: string;
  devilSteelman: string;
  angelRespond: string;
  devilRespond: string;
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
 * Angel steel-mans Devil's argument
 */
async function angelSteelmanNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  log.info(`AngelDevilGraph: Angel steelman for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-steelman'), {
      role: 'Angel',
      opposing_role: 'Devil',
      question: state.question,
      opposing_argument: state.devilResponse,
    });

    const response = await chatCompletion({
      model: state.steelmanModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      angelSteelman: extractContent(response),
      angelSteelmanModel: response.model,
      traversedNodes: [...state.traversedNodes, 'angel_steelman'],
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
 * Devil steel-mans Angel's argument
 */
async function devilSteelmanNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  log.info(`AngelDevilGraph: Devil steelman for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-steelman'), {
      role: 'Devil',
      opposing_role: 'Angel',
      question: state.question,
      opposing_argument: state.angelResponse,
    });

    const response = await chatCompletion({
      model: state.steelmanModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      devilSteelman: extractContent(response),
      devilSteelmanModel: response.model,
      traversedNodes: [...state.traversedNodes, 'devil_steelman'],
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
 * Angel responds to Devil's steel-manned argument
 */
async function angelRespondNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  log.info(`AngelDevilGraph: Angel response for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-respond'), {
      role: 'Angel',
      opposing_role: 'Devil',
      question: state.question,
      role_argument: state.angelResponse,
      opposing_steelman: state.angelSteelman,
    });

    const response = await chatCompletion({
      model: state.steelmanModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      angelRespond: extractContent(response),
      angelRespondModel: response.model,
      traversedNodes: [...state.traversedNodes, 'angel_respond'],
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
 * Devil responds to Angel's steel-manned argument
 */
async function devilRespondNode(state: AngelDevilGraphState): Promise<AngelDevilGraphState> {
  log.info(`AngelDevilGraph: Devil response for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ANGEL_DEVIL);
    const prompt = renderTemplate(loadPrompt('angel-devil-respond'), {
      role: 'Devil',
      opposing_role: 'Angel',
      question: state.question,
      role_argument: state.devilResponse,
      opposing_steelman: state.devilSteelman,
    });

    const response = await chatCompletion({
      model: state.steelmanModelGroup,
      messages: [{ role: 'user', content: prompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      devilRespond: extractContent(response),
      devilRespondModel: response.model,
      traversedNodes: [...state.traversedNodes, 'devil_respond'],
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
    const prompt = renderTemplate(loadPrompt('angel-devil-judge'), {
      question: state.question,
      angel_argument: state.angelResponse,
      devil_argument: state.devilResponse,
      angel_steelman: state.angelSteelman,
      devil_steelman: state.devilSteelman,
      angel_response: state.angelRespond,
      devil_response: state.devilRespond,
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
      traversedNodes: ['start', 'angel', 'devil', 'angel_steelman', 'devil_steelman', 'angel_respond', 'devil_respond', 'judge'],
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
      nodeCount: 8,
      angelModel: state.angelModel,
      devilModel: state.devilModel,
      angelSteelmanModel: state.angelSteelmanModel,
      devilSteelmanModel: state.devilSteelmanModel,
      angelRespondModel: state.angelRespondModel,
      devilRespondModel: state.devilRespondModel,
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
        angelModelGroup = 'angel-devil-tier2';
      }

      const initialState: AngelDevilGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.ANGEL_DEVIL,
        question: options.initialPrompt,
        angelModelGroup,
        devilModelGroup: angelModelGroup,
        steelmanModelGroup: 'angel-devil-tier3',
        judgeModelGroup: 'angel-devil-tier3',
        angelModel: '',
        devilModel: '',
        angelSteelmanModel: '',
        devilSteelmanModel: '',
        angelRespondModel: '',
        devilRespondModel: '',
        judgeModel: '',
        angelResponse: '',
        devilResponse: '',
        angelSteelman: '',
        devilSteelman: '',
        angelRespond: '',
        devilRespond: '',
        finalResponse: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      // Execute flow: angel → devil → angel_steelman → devil_steelman → angel_respond → devil_respond → judge
      let state = await angelNode(initialState);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.angelModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await devilNode(state);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.devilModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await angelSteelmanNode(state);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.angelSteelmanModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await devilSteelmanNode(state);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.devilSteelmanModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await angelRespondNode(state);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.angelRespondModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await devilRespondNode(state);
      if (state.status === 'error') {
        return { response: state.finalResponse, model: state.devilRespondModel, traversedNodes: state.traversedNodes, error: state.finalResponse };
      }

      state = await judgeNode(state);

      return {
        response: state.finalResponse,
        model: state.judgeModel || state.devilRespondModel || state.angelRespondModel || state.devilSteelmanModel || state.angelSteelmanModel || state.devilModel || state.angelModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.finalResponse : undefined,
      };
    },
  };
}

// Export singleton
export const angelDevilGraph = createAngelDevilGraph();
