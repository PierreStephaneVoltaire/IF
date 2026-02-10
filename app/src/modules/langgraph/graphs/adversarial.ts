/**
 * AdversarialGraph - Multi-Node Flow
 *
 * Implements adversarial validation (Generator → Red Team → Judge).
 * Uses model group-based routing:
 * - Generator/Red Team: general-tier2
 * - Judge: general-tier3
 *
 * Flow: start → generate → red_team → judge → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, tagsToModelGroup } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:ADVERSARIAL');

// ============================================================================
// Graph State
// ============================================================================

interface AdversarialGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  prompt: string;
  generatorModelGroup: string;
  redTeamModelGroup: string;
  judgeModelGroup: string;
  generatorModel: string;
  redTeamModel: string;
  judgeModel: string;
  solution: string;
  findings: string;
  patches: string[];
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Generate initial solution
 */
async function generateNode(state: AdversarialGraphState): Promise<AdversarialGraphState> {
  log.info(`AdversarialGraph: Generating solution for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ADVERSARIAL_VALIDATION);
    const systemPrompt = loadPrompt('adversarial-generator');

    const response = await chatCompletion({
      model: state.generatorModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: state.prompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      solution: extractContent(response),
      generatorModel: response.model,
      traversedNodes: ['start', 'generate'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      patches: [],
    };
  }
}

/**
 * Red team attack
 */
async function redTeamNode(state: AdversarialGraphState): Promise<AdversarialGraphState> {
  log.info(`AdversarialGraph: Red team attack for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ADVERSARIAL_VALIDATION);
    const systemPrompt = loadPrompt('adversarial-redteam');

    const response = await chatCompletion({
      model: state.redTeamModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: `${state.prompt}\n\nSolution to critique:\n${state.solution}` },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      findings: extractContent(response),
      redTeamModel: response.model,
      traversedNodes: [...state.traversedNodes, 'red_team'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      patches: [],
    };
  }
}

/**
 * Patch solution based on findings
 */
async function patchNode(state: AdversarialGraphState): Promise<AdversarialGraphState> {
  log.info(`AdversarialGraph: Patching solution for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.ADVERSARIAL_VALIDATION);
    const systemPrompt = loadPrompt('adversarial-patch-user');

    const response = await chatCompletion({
      model: state.generatorModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: `Original: ${state.solution}\n\nCritique: ${state.findings}` },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const patched = extractContent(response);
    const patches = state.patches;
    patches.push(patched);

    return {
      ...state,
      solution: patched,
      patches,
      traversedNodes: [...state.traversedNodes, 'patch'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      patches: [],
    };
  }
}

/**
 * Judge node - evaluates final solution
 */
async function judgeNode(state: AdversarialGraphState): Promise<AdversarialGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('judge');

  try {
    const params = getModelParams(FlowType.ADVERSARIAL_VALIDATION);
    const systemPrompt = loadPrompt('adversarial-judge-user');

    const response = await chatCompletion({
      model: state.judgeModelGroup,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: `Original prompt: ${state.prompt}\n\nSolution: ${state.solution}\n\nCritique: ${state.findings}\n\nPatches applied: ${state.patches.length}` },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    const judgeModel = response.model;

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'generate', 'red_team', 'patch', 'judge'],
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
      generatorModel: state.generatorModel,
      redTeamModel: state.redTeamModel,
      judgeModel,
      patches: state.patches.length,
      modelGroup: state.judgeModelGroup,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      solution: `${state.solution}\n\n---\n**Evaluation:**\n${content}`,
      judgeModel,
      status: 'complete',
      traversedNodes: [...state.traversedNodes, 'judge'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createAdversarialGraph() {
  return {
    name: 'AdversarialGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking AdversarialGraph for channel ${options.channelId}`);

      // Get model groups from options, or convert tags if provided
      let generatorModelGroup = options.modelGroup;
      if (!generatorModelGroup && options.tags && options.tags.length > 0) {
        generatorModelGroup = tagsToModelGroup(options.tags);
      }
      if (!generatorModelGroup) {
        generatorModelGroup = 'general-tier2';
      }

      const initialState: AdversarialGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.ADVERSARIAL_VALIDATION,
        prompt: options.initialPrompt,
        generatorModelGroup,
        redTeamModelGroup: generatorModelGroup,
        judgeModelGroup: 'general-tier3',
        generatorModel: '',
        redTeamModel: '',
        judgeModel: '',
        solution: '',
        findings: '',
        patches: [],
        status: 'running',
        traversedNodes: ['start'],
      };

      // Execute flow: generate → red_team → patch → judge
      let state = await generateNode(initialState);
      state = await redTeamNode(state);
      state = await patchNode(state);
      state = await judgeNode(state);

      return {
        response: state.solution,
        model: state.judgeModel || state.generatorModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.solution : undefined,
      };
    },
  };
}

// Export singleton
export const adversarialGraph = createAdversarialGraph();
