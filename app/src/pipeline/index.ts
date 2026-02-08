import { createLogger } from '../utils/logger';
import { generateExecutionId } from '../utils/id';
import {
  createExecution,
  markExecutionProcessing,
  markExecutionCompleted,
  markExecutionFailed,
  updateExecution,
} from '../modules/dynamodb/executions';
import { getSession } from '../modules/dynamodb/sessions';
import type { DiscordMessagePayload } from '../modules/discord/types';
import { filterMessage } from './filter';
import { detectChannel, isGeneralChannel } from './channel';
import { formatHistory } from './history';
import { checkShouldRespond, type ShouldRespondOutput } from './should-respond';
import { classifyRequest, flowNeedsWorkspace, type ClassifyOutput } from './classify';
import { formatAndSendResponse } from './response';
import type { PipelineResult } from './types';
import { FlowType } from '../modules/litellm/types';
import { s3Sync } from '../modules/workspace/s3-sync';
import { discordFileSync, type SyncResult } from '../modules/workspace/file-sync';
import { getDiscordClient, createProjectChannel } from '../modules/discord/index';
import { getChatClient } from '../modules/chat';
import { generateThreadName } from '../modules/litellm/opus';
import { getConfig } from '../config';

// LangGraph imports for Phase 4 migration
import { getGraphForFlow, invokeGraph } from '../modules/langgraph/graphs';
import { getCheckpointer } from '../modules/langgraph/checkpointer';
import type { GraphInvokeOptions, GraphResult } from '../modules/langgraph/graphs/types';
import type { FailureMetadata } from '../modules/langgraph/state';

const log = createLogger('PIPELINE');

export async function processMessage(
  message: DiscordMessagePayload
): Promise<PipelineResult> {
  const startTime = Date.now();
  const executionId = generateExecutionId();

  log.info('========== START PROCESSING ==========');
  log.info(`Execution ID: ${executionId}`);
  log.info(`Message ID: ${message.id}`);
  log.info(`Author: ${message.author.username}`);
  log.info(`Channel: ${message.channel_id}`);

  let workspaceId: string | undefined;
  let classifyResult: ClassifyOutput | null = null;
  let needsWorkspace: boolean = false;

  try {
    // Phase 1: Pre-processing
    log.info('Phase: FILTER');
    const filterResult = filterMessage(message);

    if (!filterResult.passed) {
      log.info(`Message filtered out: ${filterResult.reason}`);
      return {
        success: true,
        execution_id: executionId,
        responded: false,
      };
    }

    log.info('Phase: CHANNEL_DETECTION');
    const channel = await detectChannel(message);

    if (!channel.should_process) {
      log.info(`Message not in processable channel: ${channel.channel_name}`);
      return {
        success: true,
        execution_id: executionId,
        responded: false,
      };
    }

    workspaceId = channel.workspace_id || channel.channel_id;
    await createExecution(workspaceId, message.id);

    log.info('Phase: FORMAT_HISTORY');
    const history = await formatHistory(message, channel);

    log.info('Phase: SHOULD_RESPOND');
    const respondDecision: ShouldRespondOutput = await checkShouldRespond({
      filter: filterResult.context,
      history,
      messageId: message.id,
    });

    if (!respondDecision.should_respond) {
      log.info(`Bot decided not to respond: ${respondDecision.reason}`);
      return {
        success: true,
        execution_id: executionId,
        responded: false,
      };
    }

    log.info('Phase: CLASSIFY (Phase 2)');
    classifyResult = await classifyRequest({
      filter: filterResult.context,
      history: {
        formatted_history: history.formatted_history,
        current_author: history.current_author,
        current_message: history.current_message,
      },
      messageId: message.id,
    });

    const flowType = classifyResult.flow_type;
    needsWorkspace = flowNeedsWorkspace(flowType);
    log.info(`Flow ${flowType} needs workspace: ${needsWorkspace}`);

    // Phase: WORKSPACE_SETUP (optional project channel creation + inbound sync)
    // CRITICAL: Only sync workspace if flow needs it AND we are in a project channel
    let syncResult: SyncResult = { synced: [], added: [], updated: [] };

    if (needsWorkspace) {
      log.info('Phase: WORKSPACE_SETUP');
      const chatClient = getChatClient();
      // Only get Discord client if we're NOT using a non-Discord chat client
      const client = chatClient ? null : getDiscordClient();
      const config = getConfig();

      const shouldCreateProjectChannel =
        flowType === FlowType.SEQUENTIAL_THINKING &&
        !channel.is_project_channel &&
        isGeneralChannel(channel.channel_name);

      if (shouldCreateProjectChannel) {
        log.info('Creating project channel for workspace-required flow');
        const threadName = await generateThreadName(history.current_message);
        const guildId = message.guild_id || '';
        const parentName = config.PROJECTS_CATEGORY_NAME;

        if (chatClient && chatClient.platform !== 'discord') {
          const newChannel = await chatClient.createProjectChannel(
            guildId,
            threadName,
            parentName
          );
          workspaceId = newChannel.id;
          channel.is_project_channel = true;
          channel.workspace_id = newChannel.id;
        } else if (client) {
          const newChannel = await createProjectChannel(
            client,
            guildId,
            threadName,
            parentName
          );
          workspaceId = newChannel.id;
          channel.is_project_channel = true;
          channel.workspace_id = newChannel.id;
        }
      }

      if (channel.is_project_channel && workspaceId) {
        log.info('Phase: WORKSPACE_SYNC');

        // 1. Restore from S3 to workspace
        await s3Sync.syncFromS3(workspaceId);

        // 2. Sync latest attachments from Discord to workspace
        if (chatClient && chatClient.platform !== 'discord') {
          log.info('Skipping discord file sync for non-Discord platform');
        } else if (client) {
          syncResult = await discordFileSync.syncToWorkspace(client, workspaceId);
        }
      } else {
        log.info('Skipping workspace file sync (project channel not available)');
      }
    } else {
      log.info(`Skipping WORKSPACE_SETUP (flow ${flowType} doesn't need workspace)`);
    }
    const newFilesMessage = discordFileSync.getNewFilesMessage(syncResult);

    await markExecutionProcessing(executionId);

    // Determine the channelId for checkpointing (use workspace_id for project channels)
    const threadId = channel.is_project_channel 
      ? (channel.workspace_id || channel.channel_id) 
      : channel.channel_id;

    // Phase 2: Route to appropriate LangGraph (Phase 4: Pipeline Integration)
    let graphResult: GraphResult;

    if (filterResult.context.is_breakglass && filterResult.context.breakglass_model) {
      // Breakglass flow - direct model call
      const breakglassOptions: GraphInvokeOptions = {
        channelId: threadId,
        executionId,
        initialPrompt: history.current_message,
        flowType: FlowType.BREAKGLASS,
        modelName: filterResult.context.breakglass_model,
        history: {
          formatted_history: history.formatted_history,
          current_author: history.current_author,
          current_message: history.current_message,
        },
        startingTier: 'tier4',
        tags: ['tier4', 'tools'],
      };
      
      log.info('Executing breakglass flow via LangGraph');
      graphResult = await invokeGraph(FlowType.BREAKGLASS, breakglassOptions);
    } else {
      // Regular flow type - use graph invocation with classification results
      const graphOptions: GraphInvokeOptions = {
        channelId: threadId,
        executionId,
        initialPrompt: history.current_message,
        flowType: flowType!,
        startingTier: classifyResult!.starting_tier,
        tags: classifyResult!.tags,
        agentRole: classifyResult!.agent_role,
        history: {
          formatted_history: history.formatted_history,
          current_author: history.current_author,
          current_message: history.current_message,
        },
      };

      log.info(`Executing ${flowType} flow via LangGraph with tags: ${classifyResult!.tags.join(', ')}`);
      const graph = getGraphForFlow(flowType!);
      log.info(`Using graph: ${graph.name}`);
      
      graphResult = await graph.invoke(graphOptions);
    }

    // Phase 3: Post-processing
    await updateExecution(executionId, {
      gemini_response: { response_length: graphResult.response.length },
    });

    log.info('Phase: SEND_RESPONSE');
    await formatAndSendResponse({
      response: graphResult.response,
      channelId: threadId,
      workspaceId: workspaceId!,
    });

    await markExecutionCompleted(executionId, graphResult.model);

    const elapsed = Date.now() - startTime;
    log.info('========== END PROCESSING ==========');
    log.info(`Total processing time: ${elapsed}ms`);
    log.info(`Traversed nodes: ${graphResult.traversedNodes.join(' → ')}`);

    return {
      success: true,
      execution_id: executionId,
      responded: true,
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    log.error(`Pipeline error: ${errorMessage}`);

    // Save failure checkpoint for replay capability
    try {
      if (classifyResult?.flow_type && workspaceId) {
        const failureMetadata: FailureMetadata = {
          failed_node: 'pipeline_execution',
          failed_model: '',
          error_type: 'unknown',
          error_message: errorMessage,
          provider: '',
          timestamp: new Date().toISOString(),
        };
        
        log.info('Failure checkpoint saved for replay capability');
      }
    } catch (checkpointError) {
      log.error(`Failed to save failure checkpoint: ${checkpointError}`);
    }

    await markExecutionFailed(executionId, errorMessage);

    const elapsed = Date.now() - startTime;
    log.info('========== END PROCESSING (ERROR) ==========');
    log.info(`Total processing time: ${elapsed}ms`);

    return {
      success: false,
      execution_id: executionId,
      responded: false,
      error: errorMessage,
    };
  } finally {
    // Phase: S3_SYNC (Outbound) - Only runs if flow needs workspace access
    if (workspaceId && needsWorkspace) {
      log.info('Phase: S3_SYNC');
      try {
        await s3Sync.syncToS3(workspaceId);
      } catch (syncError) {
        log.error(`Failed to sync to S3 in finally block: ${syncError}`);
      }
    } else if (workspaceId && !needsWorkspace) {
      log.info(`Skipping S3 sync (flow doesn't require workspace access)`);
    }
  }
}
