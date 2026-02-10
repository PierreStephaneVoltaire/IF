/**
 * BackcastingGraph - Multi-Node Flow
 *
 * Implements backward planning from goal to present.
 * Uses model group-based routing:
 * - Goal/Milestones: general-tier2
 * - Feasibility: general-tier3-thinking
 *
 * Flow: start → define_goal → milestones → feasibility → action_plan → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion, extractContent, tagsToModelGroup } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:BACKCASTING');

// ============================================================================
// Graph State
// ============================================================================

interface BackcastingGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  prompt: string;
  goalModelGroup: string;
  milestoneModelGroup: string;
  feasibilityModelGroup: string;
  actionPlanModelGroup: string;
  goalModel: string;
  milestoneModel: string;
  feasibilityModel: string;
  actionPlanModel: string;
  goalState: string;
  timeline: Array<{ timepoint: string; milestone: string; prerequisites: string[] }>;
  isFeasible: boolean;
  issues: string[];
  actionPlan: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Define goal state
 */
async function defineGoalNode(state: BackcastingGraphState): Promise<BackcastingGraphState> {
  log.info(`BackcastingGraph: Defining goal for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.BACKCASTING);
    const prompt = renderTemplate(loadPrompt('backcasting-define-goal-user'), {
      question: state.prompt,
    });

    const response = await chatCompletion({
      model: state.goalModelGroup,
      messages: [
        { role: 'system', content: loadPrompt('backcasting-define-goal') },
        { role: 'user', content: prompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    return {
      ...state,
      goalState: extractContent(response),
      goalModel: response.model,
      traversedNodes: ['start', 'define_goal'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      actionPlan: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Define milestones
 */
async function milestonesNode(state: BackcastingGraphState): Promise<BackcastingGraphState> {
  try {
    const params = getModelParams(FlowType.BACKCASTING);
    const prompt = renderTemplate(loadPrompt('backcasting-milestones-user'), {
      goal: state.goalState,
    });

    const response = await chatCompletion({
      model: state.milestoneModelGroup,
      messages: [
        { role: 'system', content: loadPrompt('backcasting-milestones') },
        { role: 'user', content: prompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    // Parse timeline from response (simplified)
    const timeline: BackcastingGraphState['timeline'] = [];
    const lines = content.split('\n').filter(l => l.trim().length > 0);
    
    for (const line of lines) {
      const timepointMatch = line.match(/^[\[\(]?(\d+)[\]\)]?[\s:]+(.+)/);
      if (timepointMatch) {
        timeline.push({
          timepoint: timepointMatch[1],
          milestone: timepointMatch[2],
          prerequisites: [],
        });
      }
    }

    return {
      ...state,
      timeline,
      milestoneModel: response.model,
      traversedNodes: [...state.traversedNodes, 'milestones'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      actionPlan: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Check feasibility
 */
async function feasibilityNode(state: BackcastingGraphState): Promise<BackcastingGraphState> {
  log.info(`BackcastingGraph: Checking feasibility for channel ${state.channelId}`);

  try {
    const params = getModelParams(FlowType.BACKCASTING);
    const prompt = renderTemplate(loadPrompt('backcasting-feasibility-user'), {
      goal: state.goalState,
      milestones: state.timeline.map(t => `${t.timepoint}: ${t.milestone}`).join('\n'),
    });

    const response = await chatCompletion({
      model: state.feasibilityModelGroup,
      messages: [
        { role: 'system', content: loadPrompt('backcasting-feasibility') },
        { role: 'user', content: prompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    const isFeasible = content.toLowerCase().includes('feasible') && !content.toLowerCase().includes('not feasible');
    const issues = content.split('\n').filter(l => l.toLowerCase().includes('issue') || l.toLowerCase().includes('problem'));

    return {
      ...state,
      isFeasible,
      issues,
      feasibilityModel: response.model,
      traversedNodes: [...state.traversedNodes, 'feasibility'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      actionPlan: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Generate action plan
 */
async function actionPlanNode(state: BackcastingGraphState): Promise<BackcastingGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('action_plan');

  try {
    const params = getModelParams(FlowType.BACKCASTING);
    const prompt = renderTemplate(loadPrompt('backcasting-action-plan-user'), {
      goal: state.goalState,
      milestones: state.timeline.map(t => `${t.timepoint}: ${t.milestone}`).join('\n'),
      feasibility: state.isFeasible ? 'Feasible' : 'Not Feasible',
      issues: state.issues.join('\n'),
    });

    const response = await chatCompletion({
      model: state.actionPlanModelGroup,
      messages: [
        { role: 'system', content: loadPrompt('backcasting-action-plan') },
        { role: 'user', content: prompt },
      ],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const content = extractContent(response);
    const actionPlanModel = response.model;

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'define_goal', 'milestones', 'feasibility', 'action_plan'],
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
      goalModel: state.goalModel,
      milestoneModel: state.milestoneModel,
      feasibilityModel: state.feasibilityModel,
      actionPlanModel,
      isFeasible: state.isFeasible,
      milestonesCount: state.timeline.length,
      modelGroup: state.actionPlanModelGroup,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      actionPlan: content,
      actionPlanModel,
      status: 'complete',
      traversedNodes: [...state.traversedNodes, 'action_plan'],
    };
  } catch (error) {
    return {
      ...state,
      status: 'error',
      actionPlan: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createBackcastingGraph() {
  return {
    name: 'BackcastingGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking BackcastingGraph for channel ${options.channelId}`);

      // Get model groups from options, or convert tags if provided
      let goalModelGroup = options.modelGroup;
      if (!goalModelGroup && options.tags && options.tags.length > 0) {
        goalModelGroup = tagsToModelGroup(options.tags);
      }
      if (!goalModelGroup) {
        goalModelGroup = 'general-tier2';
      }

      const initialState: BackcastingGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.BACKCASTING,
        prompt: options.initialPrompt,
        goalModelGroup,
        milestoneModelGroup: goalModelGroup,
        feasibilityModelGroup: 'general-tier3-thinking',
        actionPlanModelGroup: goalModelGroup,
        goalModel: '',
        milestoneModel: '',
        feasibilityModel: '',
        actionPlanModel: '',
        goalState: '',
        timeline: [],
        isFeasible: true,
        issues: [],
        actionPlan: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      // Execute flow: goal → milestones → feasibility → action_plan
      let state = await defineGoalNode(initialState);
      if (state.status === 'error') {
        return { response: state.actionPlan, model: state.goalModel, traversedNodes: state.traversedNodes, error: state.actionPlan };
      }

      state = await milestonesNode(state);
      state = await feasibilityNode(state);
      state = await actionPlanNode(state);

      return {
        response: state.actionPlan,
        model: state.actionPlanModel || state.feasibilityModel || state.milestoneModel || state.goalModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.actionPlan : undefined,
      };
    },
  };
}

// Export singleton
export const backcastingGraph = createBackcastingGraph();
