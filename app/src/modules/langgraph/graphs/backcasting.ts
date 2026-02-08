/**
 * BackcastingGraph - Backcasting Flow
 *
 * A backward planning flow for long-term goals. Works from future state to present:
 * - Define Goal (tier2): User states desired future state + timeline
 * - Milestone Generator (tier3): Work BACKWARD from goal to present
 * - Feasibility Check (tier3): Review backward path for contradictions
 * - Action Plan: Present → Goal roadmap
 *
 * Flow: start → define_goal → generate_milestones → feasibility_check → action_plan → finalize
 */

import { createLogger } from '../../../utils/logger';
import { chatCompletion } from '../../litellm/index';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import { loadPrompt, renderTemplate } from '../../../templates/loader';
import type { GraphResult, GraphInvokeOptions } from './types';
import type { LogEntry } from '../state';

const log = createLogger('GRAPH:BACKCASTING');

// ============================================================================
// Graph State
// ============================================================================

interface BackcastingGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  initialPrompt: string;
  goalDefinition: string;
  goalModel: string;
  milestoneModel: string;
  feasibilityModel: string;
  timeline: string;
  goalState: string;
  milestones: Array<{
    timepoint: string;
    milestone: string;
    prerequisites: string[];
  }>;
  feasibilityIssues: string[];
  actionPlan: string;
  isFeasible: boolean;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
  logBuffer: LogEntry[];
}

// ============================================================================
// Helper Functions
// ============================================================================

async function defineGoal(prompt: string, tags: string[]): Promise<{
  goalState: string;
  timeline: string;
}> {
  const systemPrompt = await loadPrompt('backcasting-define-goal');
  const userPrompt = renderTemplate(await loadPrompt('backcasting-define-goal-user'), {
    goal_request: prompt,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.6,
    top_p: 0.85,
    metadata: { tags },
  });

  const content = response.choices[0]?.message?.content || '{}';
  
  try {
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const result = JSON.parse(jsonMatch[0]);
      return {
        goalState: result.goal_state || content,
        timeline: result.timeline || 'Not specified',
      };
    }
    return { goalState: content, timeline: 'Not specified' };
  } catch {
    return { goalState: content, timeline: 'Not specified' };
  }
}

async function generateMilestones(
  goalState: string,
  timeline: string,
  tags: string[]
): Promise<Array<{
  timepoint: string;
  milestone: string;
  prerequisites: string[];
}>> {
  const systemPrompt = await loadPrompt('backcasting-milestones');
  const userPrompt = renderTemplate(await loadPrompt('backcasting-milestones-user'), {
    goal_state: goalState,
    timeline: timeline,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });

  const content = response.choices[0]?.message?.content || '[]';
  
  try {
    const jsonMatch = content.match(/\[[\s\S]*\]/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
    return [];
  } catch {
    return [];
  }
}

async function checkFeasibility(
  goalState: string,
  milestones: Array<{ timepoint: string; milestone: string; prerequisites: string[] }>,
  tags: string[]
): Promise<{ issues: string[]; isFeasible: boolean }> {
  const milestoneText = milestones.map(m =>
    `${m.timepoint}: ${m.milestone}\nPrerequisites: ${m.prerequisites.join(', ')}`
  ).join('\n\n');

  const systemPrompt = await loadPrompt('backcasting-feasibility');
  const userPrompt = renderTemplate(await loadPrompt('backcasting-feasibility-user'), {
    goal_state: goalState,
    milestone_text: milestoneText,
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.6,
    top_p: 0.85,
    metadata: { tags },
  });

  const content = response.choices[0]?.message?.content || '';
  const issues: string[] = [];
  
  // Parse issues from response
  if (content.toLowerCase().includes('no significant issues') ||
      content.toLowerCase().includes('no major issues')) {
    return { issues: [], isFeasible: true };
  }

  // Extract potential issues
  const lines = content.split('\n').filter(l => l.trim().length > 0);
  for (const line of lines) {
    if (line.match(/^\d+\.|^[-•*]/) && line.length > 10) {
      issues.push(line.replace(/^\d+\.\s*|^[-•*]\s*/, '').trim());
    }
  }

  return {
    issues: issues.length > 0 ? issues : [content],
    isFeasible: issues.length < 3,
  };
}

async function generateActionPlan(
  goalState: string,
  timeline: string,
  milestones: Array<{ timepoint: string; milestone: string; prerequisites: string[] }>,
  feasibilityIssues: string[],
  isFeasible: boolean,
  tags: string[]
): Promise<string> {
  const milestoneText = milestones.map(m =>
    `**${m.timepoint}**: ${m.milestone}\n   Prerequisites: ${m.prerequisites.join(', ')}`
  ).join('\n\n');

  const issuesText = feasibilityIssues.length > 0
    ? `**Feasibility Concerns**:\n${feasibilityIssues.map(i => `- ${i}`).join('\n')}`
    : '✓ No significant feasibility issues identified';

  const systemPrompt = await loadPrompt('backcasting-action-plan');
  const userPrompt = renderTemplate(await loadPrompt('backcasting-action-plan-user'), {
    goal_state: goalState,
    timeline: timeline,
    milestone_text: milestoneText,
    feasibility_text: issuesText,
    is_feasible: isFeasible ? 'Yes' : 'Requires revision',
  });
  
  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.7,
    top_p: 0.9,
    metadata: { tags },
  });

  return response.choices[0]?.message?.content || 'Unable to generate action plan';
}

async function finalizeGraph(state: BackcastingGraphState): Promise<GraphResult> {
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

  const milestoneSection = state.milestones.map(m =>
    `**${m.timepoint}**: ${m.milestone}\n   _Prerequisites: ${m.prerequisites.join(', ') || 'None'}_`
  ).join('\n\n');

  const issuesSection = state.feasibilityIssues.length > 0
    ? `**Feasibility Review**:\n${state.feasibilityIssues.map(i => `- ${i}`).join('\n')}`
    : '✓ No significant feasibility issues';

  const finalResponse = `## Backcasting Plan Complete\n\n**Goal:** ${state.goalState}\n\n**Timeline:** ${state.timeline}\n\n### Backward Milestones:\n${milestoneSection}\n\n${issuesSection}\n\n### Action Plan:\n${state.actionPlan}\n\n**Feasibility:** ${state.isFeasible ? '✓ Path appears viable' : '⚠ Requires careful consideration of issues'}\n\n**Status:** ${state.status}`;

  const metadata = {
    flowType: state.flowType,
    channelId: state.channelId,
    executionId: state.executionId,
    status: 'complete',
    nodeCount: state.traversedNodes.length + 1,
    model: state.feasibilityModel,
    tags: ['tier3', 'thinking'],
    milestonesCount: state.milestones.length,
    isFeasible: state.isFeasible,
    timestamp: new Date().toISOString(),
  };

  await logger.uploadMetadata(metadata);
  await logger.flush();

  return {
    response: finalResponse,
    model: state.feasibilityModel,
    traversedNodes: state.traversedNodes,
  };
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createBackcastingGraph() {
  return {
    name: 'BackcastingGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking BackcastingGraph for channel ${options.channelId}`);

      const state: BackcastingGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.BACKCASTING,
        initialPrompt: options.initialPrompt,
        goalDefinition: '',
        goalModel: 'auto',
        milestoneModel: 'auto',
        feasibilityModel: 'auto',
        timeline: '',
        goalState: '',
        milestones: [],
        feasibilityIssues: [],
        actionPlan: '',
        isFeasible: true,
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

        // Step 1: Define goal
        logger.recordNode('define_goal');
        const goalResult = await defineGoal(state.initialPrompt, ['tier2', 'general']);
        state.goalState = goalResult.goalState;
        state.timeline = goalResult.timeline;
        state.traversedNodes.push('define_goal');
        log.info('Goal defined');

        // Step 2: Generate backward milestones
        logger.recordNode('generate_milestones');
        state.milestones = await generateMilestones(
          state.goalState,
          state.timeline,
          ['tier3', 'thinking']
        );
        state.traversedNodes.push('generate_milestones');
        log.info(`Generated ${state.milestones.length} milestones`);

        // Step 3: Check feasibility
        logger.recordNode('feasibility_check');
        const feasibilityResult = await checkFeasibility(
          state.goalState,
          state.milestones,
          ['tier3', 'thinking']
        );
        state.feasibilityIssues = feasibilityResult.issues;
        state.isFeasible = feasibilityResult.isFeasible;
        state.traversedNodes.push('feasibility_check');
        log.info(`Feasibility check complete. Feasible: ${state.isFeasible}`);

        // Step 4: Generate action plan
        logger.recordNode('action_plan');
        state.actionPlan = await generateActionPlan(
          state.goalState,
          state.timeline,
          state.milestones,
          state.feasibilityIssues,
          state.isFeasible,
          ['tier3', 'thinking']
        );
        state.traversedNodes.push('action_plan');
        log.info('Action plan generated');

        state.status = 'complete';
        return await finalizeGraph(state);

      } catch (error) {
        log.error(`Backcasting error: ${error}`);
        state.status = 'error';

        const metadata = {
          flowType: state.flowType,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'error',
          error: String(error),
          tags: ['tier3', 'thinking'],
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
export const backcastingGraph = createBackcastingGraph();
