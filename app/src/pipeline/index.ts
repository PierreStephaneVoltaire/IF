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
import { checkShouldRespond } from './should-respond';
import { classifyFlow } from './classify';
import { formatAndSendResponse } from './response';
import {
  executeBreakglassFlow,
  executeSequentialThinkingFlow, // Renamed from agentic
  executeBranchFlow,             // NEW
  executeSimpleFlow,
  executeShellFlow,              // NEW: Shell command suggestions
  executeArchitectureFlow,       // NEW: Architecture/design flow
  executeSocialFlow,             // NEW: Social interactions (tier 1)
  executeProofreaderFlow,        // NEW: Grammar/spellcheck (tier 1)
  executeDialecticFlow,          // NEW: Dialectic Synthesis (philosophical)
  executeConsensusFlow,          // NEW: Multi-Source Consensus (factual)
  executeAngelDevilFlow,         // NEW: Angel/Devil Debate (moral/ethical)
  type FlowContext,
} from './flows';
import { flowNeedsWorkspace } from './classify';
import type { PipelineResult } from './types';
import { FlowType } from '../modules/litellm/types';
import { s3Sync } from '../modules/workspace/s3-sync';
import { discordFileSync, type SyncResult } from '../modules/workspace/file-sync';
import { getDiscordClient, createProjectChannel } from '../modules/discord/index';
import { getChatClient } from '../modules/chat';
import { generateThreadName } from '../modules/litellm/opus';
import { getConfig } from '../config';
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
  let flowType: FlowType | null = null;
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
    const respondDecision = await checkShouldRespond({
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

    log.info('Phase: CLASSIFY');

    // Get session for confidence score
    // Only if workspaceId is defined, otherwise skip session lookup
    let confidenceScore = 0.5; // Default value
    if (workspaceId) {
      const session = await getSession(workspaceId);
      confidenceScore = session?.confidence_score ?? 0.5;
    }

    flowType = classifyFlow(
      respondDecision.is_technical,
      respondDecision.task_type,
      false,
      filterResult.context,
      message.content,
      confidenceScore
    );

    // Determine if this flow needs workspace access
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
        respondDecision.is_technical &&
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
        // CRITICAL: Only sync if we are in a project channel. NOT the main channel.
        // Syncing main channel would download ALL history attachments.
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

    // Build flow context
    const flowContext: FlowContext = {
      workspaceId: workspaceId!,
      channelId: channel.is_project_channel ? (channel.workspace_id || channel.channel_id) : channel.channel_id,
      messageId: message.id,
      history,
      filterContext: filterResult.context,
      isProjectChannel: channel.is_project_channel,
      needsWorkspace,
      executionId,
      userAddedFilesMessage: newFilesMessage, // Pass to flows
      parentName: channel.parent_name ?? null,
    };

    // Phase 2: Route to appropriate flow
    let flowResult;

    if (filterResult.context.is_breakglass && filterResult.context.breakglass_model) {
      flowResult = await executeBreakglassFlow(
        flowContext,
        filterResult.context.breakglass_model
      );
    } else {
      // Flow type has already been classified above and stored in flowType
      switch (flowType) {
        case FlowType.SEQUENTIAL_THINKING:
          flowResult = await executeSequentialThinkingFlow(flowContext, message);
          break;
        case FlowType.ARCHITECTURE:
          flowResult = await executeArchitectureFlow(flowContext, message);
          break;
        case FlowType.SOCIAL:
          flowResult = await executeSocialFlow(flowContext);
          break;
        case FlowType.PROOFREADER:
          flowResult = await executeProofreaderFlow(flowContext);
          break;
        case FlowType.DIALECTIC:
          flowResult = await executeDialecticFlow(flowContext);
          break;
        case FlowType.CONSENSUS:
          flowResult = await executeConsensusFlow(flowContext);
          break;
        case FlowType.ANGEL_DEVIL:
          flowResult = await executeAngelDevilFlow(flowContext);
          break;
        // case FlowType.BRANCH:
        //   flowResult = await executeBranchFlow(flowContext);
        //   break;
        case FlowType.SHELL:
          flowResult = await executeShellFlow(flowContext);
          break;
        case FlowType.SIMPLE:
        default:
          flowResult = await executeSimpleFlow(
            flowContext,
            respondDecision.task_type
          );
          break;
      }
    }

    // Phase 3: Post-processing
    await updateExecution(executionId, {
      gemini_response: { response_length: flowResult!.response.length },
    });

    log.info('Phase: SEND_RESPONSE');
    await formatAndSendResponse({
      response: flowResult!.response,
      channelId: flowResult!.responseChannelId,
      workspaceId: workspaceId!,
    });

    await markExecutionCompleted(executionId, flowResult!.model);

    const elapsed = Date.now() - startTime;
    log.info('========== END PROCESSING ==========');
    log.info(`Total processing time: ${elapsed}ms`);

    return {
      success: true,
      execution_id: executionId,
      responded: true,
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    log.error(`Pipeline error: ${errorMessage}`);

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
    // This prevents unnecessary S3 syncs for social, proofreader flows that don't need persistence
    if (workspaceId && needsWorkspace) {
      log.info('Phase: S3_SYNC');
      try {
        await s3Sync.syncToS3(workspaceId);
      } catch (syncError) {
        log.error(`Failed to sync to S3 in finally block: ${syncError}`);
      }
    } else if (workspaceId && !needsWorkspace) {
      log.info(`Skipping S3 sync (flow ${flowType} doesn't require workspace access)`);
    }
  }
}
