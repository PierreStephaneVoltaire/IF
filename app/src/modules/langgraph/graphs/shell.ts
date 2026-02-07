/**
 * ShellGraph - Single Node Flow
 *
 * A simple graph for shell command suggestions.
 * - Suggests 1-3 ready-to-execute one-liner commands
 * - No multi-line scripts (if user wants scripts, they should use coding flow)
 * - If OS not specified, provides both Linux and Windows versions
 * - Commands are complete with no placeholders
 * - Uses a random tier 2 model (no tools needed)
 *
 * Flow: start → suggest → finalize
 *
 * @see plans/langgraph-migration-plan.md
 */

import { createLogger } from '../../../utils/logger';
import { executeSimpleTask } from '../../litellm/executor';
import { getModelParams } from '../temperature';
import { FlowType, TaskType } from '../../litellm/types';
import { getPromptForTaskType, getModelForTaskType } from '../../../templates/registry';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions, MessageHistory } from './types';

const log = createLogger('GRAPH:SHELL');

// ============================================================================
// Graph State
// ============================================================================

interface ShellGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  message: string;
  history?: MessageHistory;
  workspaceId: string;
  model: string;
  response: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Suggest node - generates shell command suggestions
 */
async function suggestNode(state: ShellGraphState): Promise<ShellGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('suggest');

  log.info(`ShellGraph: Starting execution for channel ${state.channelId}`);
  log.info(`Workspace: ${state.workspaceId}`);

  try {
    // Get prompt category and model for shell commands
    const promptCategory = getPromptForTaskType(TaskType.SHELL_COMMAND);
    const model = getModelForTaskType(TaskType.SHELL_COMMAND);

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Using prompt category: ${promptCategory}, model: ${model}`);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Format the full history with current message
    const fullHistory = state.history?.formatted_history
      ? `${state.history.formatted_history}\n\n${state.history.current_author}: ${state.history.current_message}`
      : `${state.message}`;

    // Execute the task without tools (shell flow is suggestion-only)
    const response = await executeSimpleTask(
      promptCategory,
      fullHistory,
      state.workspaceId,
      model,
      false, // No tools for shell flow - just suggestions
      params
    );

    log.info(`Shell flow complete, response length: ${response.length}`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'suggest'],
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
      nodeCount: 2,
      model,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);

    // Flush logs
    await logger.flush();

    return {
      ...state,
      model,
      response,
      status: 'complete',
      traversedNodes: ['start', 'suggest'],
    };
  } catch (error) {
    log.error(`ShellGraph error: ${error}`);

    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'error',
      error: String(error),
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      status: 'error',
      response: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createShellGraph() {
  return {
    name: 'ShellGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking ShellGraph for channel ${options.channelId}`);

      const initialState: ShellGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.SHELL,
        message: options.initialPrompt,
        history: options.history,
        workspaceId: options.workspacePath || options.channelId,
        model: '',
        response: '',
        status: 'running',
        traversedNodes: ['start'],
      };

      const finalState = await suggestNode(initialState);

      return {
        response: finalState.response,
        model: finalState.model,
        traversedNodes: finalState.traversedNodes,
        error: finalState.status === 'error' ? finalState.response : undefined,
      };
    },
  };
}

// Export singleton
export const shellGraph = createShellGraph();
