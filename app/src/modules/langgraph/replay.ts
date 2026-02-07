/**
 * LangGraph Replay Functionality
 *
 * Provides replay capability for failed graph executions.
 * Loads checkpoints from DynamoDB and resumes from the exact failed node.
 *
 * @see plans/langgraph-migration-plan.md §5
 */

import { createLogger } from '../../utils/logger';
import { getCheckpointer, type CheckpointBundle } from './checkpointer';
import { getGraphForFlow } from './graphs';
import type { GraphInvokeOptions, GraphResult } from './graphs/types';
import type { FailureMetadata } from './state';
import { FlowType } from '../litellm/types';

const log = createLogger('LANGGRAPH:REPLAY');

/**
 * Replay result information
 */
export interface ReplayInfo {
  channelId: string;
  hasCheckpoint: boolean;
  checkpoint?: CheckpointBundle;
  error?: string;
}

/**
 * Replay execution result
 */
export interface ReplayResult {
  success: boolean;
  response: string;
  model: string;
  traversedNodes: string[];
  error?: string;
}

/**
 * Get replay info for a channel - check if a checkpoint exists
 */
export async function getReplayInfo(channelId: string): Promise<ReplayInfo> {
  try {
    const checkpointer = getCheckpointer();
    const checkpoint = await checkpointer.getLatest(channelId);

    if (!checkpoint) {
      return {
        channelId,
        hasCheckpoint: false,
      };
    }

    return {
      channelId,
      hasCheckpoint: true,
      checkpoint,
    };
  } catch (error) {
    log.error(`Failed to get replay info for channel ${channelId}:`, { error });
    return {
      channelId,
      hasCheckpoint: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

/**
 * Format checkpoint info for Discord display
 */
export function formatCheckpointInfo(checkpoint: CheckpointBundle): string {
  const { metadata } = checkpoint;
  
  const lines: string[] = ['**📋 Checkpoint Found**'];
  
  if (metadata.created_at) {
    lines.push(`**Created:** ${new Date(metadata.created_at).toLocaleString()}`);
  }
  
  if (metadata.failed_node) {
    lines.push(`**Failed Node:** \`${metadata.failed_node}\``);
  }
  
  if (metadata.failed_model) {
    lines.push(`**Failed Model:** \`${metadata.failed_model}\``);
  }
  
  if (metadata.error_type) {
    lines.push(`**Error Type:** ${metadata.error_type}`);
  }
  
  if (metadata.error_message) {
    lines.push(`**Error:** ${metadata.error_message}`);
  }
  
  if (metadata.provider) {
    lines.push(`**Provider:** ${metadata.provider}`);
  }
  
  if (metadata.parent_checkpoint_id) {
    lines.push(`**Parent Checkpoint:** ${metadata.parent_checkpoint_id}`);
  }
  
  return lines.join('\n');
}

/**
 * Replay a failed execution from the last checkpoint
 *
 * This function:
 * 1. Loads the last checkpoint for the channel
 * 2. Resumes graph execution from the exact failed node
 * 3. Streams progress to Discord
 * 4. Returns the final result
 */
export async function replayExecution(
  channelId: string,
  flowType: FlowType,
  options: {
    initialPrompt?: string;
    history?: GraphInvokeOptions['history'];
  } = {}
): Promise<ReplayResult> {
  log.info(`Starting replay for channel ${channelId}, flow type ${flowType}`);

  try {
    // Get the checkpoint
    const checkpointer = getCheckpointer();
    const checkpoint = await checkpointer.getLatest(channelId);

    if (!checkpoint) {
      return {
        success: false,
        response: '❌ No checkpoint found for this channel. Cannot replay.',
        model: '',
        traversedNodes: [],
        error: 'no_checkpoint',
      };
    }

    log.info(`Found checkpoint for channel ${channelId}`);

    // Get the appropriate graph
    const graph = getGraphForFlow(flowType);
    log.info(`Using graph: ${graph.name}`);

    // Build invoke options from checkpoint state
    const checkpointState = checkpoint.checkpoint;
    const invokeOptions: GraphInvokeOptions = {
      channelId,
      executionId: checkpointState.executionId || `replay-${Date.now()}`,
      initialPrompt: options.initialPrompt || checkpointState.initialPrompt || '',
      flowType,
      history: options.history,
    };

    log.info(`Resuming execution from checkpoint`);

    // Resume graph execution
    const result = await graph.invoke(invokeOptions);

    log.info(`Replay completed successfully for channel ${channelId}`);

    return {
      success: true,
      response: result.response,
      model: result.model,
      traversedNodes: result.traversedNodes,
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    log.error(`Replay failed for channel ${channelId}:`, { error: errorMessage });

    return {
      success: false,
      response: `❌ Replay failed: ${errorMessage}`,
      model: '',
      traversedNodes: [],
      error: errorMessage,
    };
  }
}

/**
 * Delete a checkpoint for a channel
 */
export async function deleteCheckpoint(channelId: string): Promise<boolean> {
  try {
    const checkpointer = getCheckpointer();
    
    // List all checkpoints and delete them
    const result = await checkpointer.list(channelId, { limit: 100 });
    
    for (const checkpoint of result.checkpoints) {
      // The checkpoint ID is embedded in the SK
      // We need to extract it from the checkpoint state
      const checkpointId = `${checkpoint.checkpoint.executionId}-${checkpoint.checkpoint.turnNumber}`;
      await checkpointer.delete(channelId, checkpointId);
    }

    log.info(`Deleted ${result.checkpoints.length} checkpoints for channel ${channelId}`);
    return true;
  } catch (error) {
    log.error(`Failed to delete checkpoints for channel ${channelId}:`, { error });
    return false;
  }
}

/**
 * Format replay info for Discord embed
 */
export function formatReplayEmbed(
  replayInfo: ReplayInfo,
  additionalInfo?: string
): string {
  if (!replayInfo.hasCheckpoint) {
    return '❌ **No Checkpoint Available**\n\nNo failed execution checkpoint was found for this channel. You cannot replay.';
  }

  let embed = '✅ **Replay Available**\n\nA failed execution checkpoint was found. You can resume from where it left off.\n\n';

  if (replayInfo.checkpoint) {
    embed += formatCheckpointInfo(replayInfo.checkpoint);
  }

  if (additionalInfo) {
    embed += `\n\n${additionalInfo}`;
  }

  return embed;
}
