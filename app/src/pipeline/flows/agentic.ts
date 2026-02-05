import { createLogger } from '../../utils/logger';
import { setupSession, updateSessionAfterExecution } from '../session';
import { processAttachments } from '../attachments';
import { createPlan } from '../planning';
import { executeSequentialThinkingLoop } from '../../modules/agentic/loop';
import { getMaxTurns, getCheckpointInterval, getModelForAgent } from '../../templates/registry';
import { generateThreadName } from '../../modules/litellm/opus';
import { getDiscordClient, createProjectChannel } from '../../modules/discord/index';
import { getConfig } from '../../config';
import { getChatClient } from '../../modules/chat';
import type { FlowContext, FlowResult } from './types';
import type { DiscordMessagePayload } from '../../modules/discord/types';

const log = createLogger('FLOW:AGENTIC');

export async function executeAgenticFlow(
  context: FlowContext,
  message: DiscordMessagePayload
): Promise<FlowResult> {
  log.info('Phase: AGENTIC_FLOW');

  // Create project channel if not already in one
  let finalThreadId = context.workspaceId;
  let responseChannelId = context.workspaceId;

  if (!context.isProjectChannel) {
    log.info('Creating project channel for agentic execution');
    const threadName = await generateThreadName(context.history.current_message);
    const chatClient = getChatClient();
    const parentName = context.parentName;
    const guildId = message.guild_id || getConfig().DISCORD_GUILD_ID;
    if (chatClient && chatClient.platform !== 'discord') {
      const newChannel = await chatClient.createProjectChannel(
        guildId,
        threadName,
        parentName || 'Projects'
      );
      finalThreadId = newChannel.id;
      responseChannelId = newChannel.id;
    } else {
      const client = getDiscordClient();
      const newChannel = await createProjectChannel(
        client,
        guildId,
        threadName,
        parentName || 'Projects'
      );
      finalThreadId = newChannel.id;
      responseChannelId = newChannel.id;
    }
  }

  // Setup session
  const sessionResult = await setupSession(finalThreadId, context.channelId);
  const branchName = sessionResult.branchName;

  // Process attachments
  const processedAttachments = await processAttachments(
    context.history.current_attachments
  );

  // Generate plan
  const planning = await createPlan({
    threadId: finalThreadId,
    branchName: sessionResult.branchName,
    session: sessionResult.session,
    history: context.history,
    processedAttachments,
  });

  // Execute agentic loop
  const maxTurns = getMaxTurns(
    planning.complexity,
    planning.estimated_turns
  );

  const agenticResult = await executeSequentialThinkingLoop(
    {
      maxTurns,
      currentTurn: 0,
      model: getModelForAgent(planning.agent_role),
      agentRole: planning.agent_role,
      tools: [], // Tools loaded inside loop
      checkpointInterval: getCheckpointInterval(planning.complexity),
    },
    planning.reformulated_prompt,
    finalThreadId
  );

  // Update session
  await updateSessionAfterExecution(
    finalThreadId,
    planning,
    context.history.current_message,
    message.timestamp,
    sessionResult.session
  );

  return {
    response: agenticResult.finalResponse,
    model: 'agentic',
    branchName,
    responseChannelId,
  };
}
