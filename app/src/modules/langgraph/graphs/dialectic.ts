/**
 * DialecticGraph - Multi-Node Flow
 *
 * Implements thesis → antithesis → synthesis pattern for philosophical discourse.
 * Uses model group-based routing:
 * - Thesis/Antithesis: websearch-tier2
 * - Synthesizer: general-tier3-thinking
 *
 * Flow: start → thesis → antithesis → synthesize → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelGroup } from '../model-tiers';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:DIALECTIC');

// ============================================================================
// Graph State
// ============================================================================

interface DialecticGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  thesisModelGroup: string;
  antithesisModelGroup: string;
  synthesizerModelGroup: string;
  thesisModel: string;
  antithesisModel: string;
  synthesizerModel: string;
  thesis: string;
  antithesis: string;
  synthesis: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Thesis node - presents the initial argument
 */
async function thesisNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('thesis');

  log.info(`DialecticGraph: Starting execution for channel ${state.channelId}`);

  try {
    const systemPrompt = loadPrompt('dialectic-thesis');
    const params = getModelParams(FlowType.DIALECTIC);

    const response = await chatCompletion({
      model: state.thesisModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: state.userQuestion },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const thesis = extractContent(response);
    const thesisModel = response.model;
    log.info(`Thesis generated: ${thesis.length} chars, model: ${thesisModel}`);

    return {
      ...state,
      thesis,
      thesisModel,
      traversedNodes: ['start', 'thesis'],
    };
  } catch (error) {
    log.error(`Dialectic thesis error: ${error}`);
    return {
      ...state,
      status: 'error',
      synthesis: `Error generating thesis: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Antithesis node - presents opposing argument
 */
async function antithesisNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('antithesis');

  try {
    const systemPrompt = loadPrompt('dialectic-antithesis');
    const params = getModelParams(FlowType.DIALECTIC);

    const response = await chatCompletion({
      model: state.antithesisModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: `${state.userQuestion}\n\nThesis: ${state.thesis}` },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const antithesis = extractContent(response);
    const antithesisModel = response.model;
    log.info(`Antithesis generated: ${antithesis.length} chars, model: ${antithesisModel}`);

    return {
      ...state,
      antithesis,
      antithesisModel,
      traversedNodes: [...state.traversedNodes, 'antithesis'],
    };
  } catch (error) {
    log.error(`Dialectic antithesis error: ${error}`);
    return {
      ...state,
      status: 'error',
      synthesis: `Error generating antithesis: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Synthesizer node - combines thesis and antithesis
 */
async function synthesizerNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('synthesize');

  try {
    const systemPrompt = loadPrompt('dialectic-synthesis');
    const params = getModelParams(FlowType.DIALECTIC);

    const response = await chatCompletion({
      model: state.synthesizerModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        {
          role: 'user',
          content: `${state.userQuestion}\n\nThesis: ${state.thesis}\n\nAntithesis: ${state.antithesis}`,
        },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const synthesis = extractContent(response);
    const synthesizerModel = response.model;
    log.info(`Synthesis generated: ${synthesis.length} chars, model: ${synthesizerModel}`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'thesis', 'antithesis', 'synthesize'],
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
      nodeCount: 4,
      thesisModel: state.thesisModel,
      antithesisModel: state.antithesisModel,
      synthesizerModel,
      modelGroup: state.synthesizerModelGroup,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      synthesis,
      synthesizerModel,
      status: 'complete',
      traversedNodes: [...state.traversedNodes, 'synthesize'],
    };
  } catch (error) {
    log.error(`Dialectic synthesis error: ${error}`);
    return {
      ...state,
      status: 'error',
      synthesis: `Error generating synthesis: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createDialecticGraph() {
  return {
    name: 'DialecticGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking DialecticGraph for channel ${options.channelId}`);

      // Get model groups from options, or use new tiered system
      let thesisModelGroup = options.modelGroup;
      if (!thesisModelGroup) {
        // Dialectic is always tier2
        thesisModelGroup = getModelGroup('dialectic', 'tier2');
      }
      // Legacy fallback: convert tags if provided
      if (!thesisModelGroup && options.tags && options.tags.length > 0) {
        const { tagsToModelGroup } = require('../../litellm/model-groups');
        thesisModelGroup = tagsToModelGroup(options.tags);
      }
      if (!thesisModelGroup) {
        thesisModelGroup = 'dialectic-tier2';
      }

      const initialState: DialecticGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.DIALECTIC,
        userQuestion: options.initialPrompt,
        thesisModelGroup,
        antithesisModelGroup: thesisModelGroup,
        synthesizerModelGroup: 'dialectic-tier3',
        thesisModel: '',
        antithesisModel: '',
        synthesizerModel: '',
        thesis: '',
        antithesis: '',
        synthesis: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      // Execute flow: thesis → antithesis → synthesize
      let state = await thesisNode(initialState);
      if (state.status === 'error') {
        return { response: state.synthesis, model: state.thesisModel, traversedNodes: state.traversedNodes, error: state.synthesis };
      }

      state = await antithesisNode(state);
      if (state.status === 'error') {
        return { response: state.synthesis, model: state.antithesisModel, traversedNodes: state.traversedNodes, error: state.synthesis };
      }

      state = await synthesizerNode(state);

      return {
        response: state.synthesis,
        model: state.synthesizerModel || state.antithesisModel || state.thesisModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.synthesis : undefined,
      };
    },
  };
}

// Export singleton
export const dialecticGraph = createDialecticGraph();
