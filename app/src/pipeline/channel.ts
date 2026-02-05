import { getDiscordClient, getChannel } from '../modules/discord/index';
import { getChatClient } from '../modules/chat';
import type { ChannelInfo } from '../modules/discord/types';
import type { ChatChannel } from '../modules/chat/types';
import { createLogger } from '../utils/logger';
import { getConfig } from '../config';
import type { DiscordMessagePayload } from '../modules/discord/types';
import type { ChannelContext } from './types';

const log = createLogger('CHANNEL');

const CHANNEL_TYPE_NAMES: Record<string, string> = {
  'text': 'TEXT_CHANNEL',
  'thread': 'THREAD',
  'dm': 'DM',
};

export async function detectChannel(
  message: DiscordMessagePayload
): Promise<ChannelContext> {
  log.info('Detecting channel context');

  const config = getConfig();
  const chatClient = getChatClient();
  // Only get Discord client if we're NOT using a chat client (i.e., we're on Discord)
  const client = chatClient ? null : getDiscordClient();
  
  const channelInfo = (chatClient
    ? await chatClient.getChannel(message.channel_id)
    : await getChannel(client!, message.channel_id)) as (ChatChannel | ChannelInfo | null);

  if (!channelInfo) {
    log.warn(`Channel info not found for ID: ${message.channel_id}`);
    return {
      is_project_channel: false,
      workspace_id: null,
      channel_id: message.channel_id,
      channel_name: 'unknown',
      channel_type: 0,
      parent_id: null,
      parent_name: null,
      should_process: true,
    };
  }

  // Handle platform-agnostic type checking
  let channelType: number;
  let parentName: string | null = null;
  let parent_id: string | null = null;
  let isThreadChannel: boolean = false;

  if ('type' in channelInfo && typeof channelInfo.type !== 'undefined') {
    // For platform-agnostic ChatChannel
    if (typeof channelInfo.type === 'string') {
      // Map string types to numeric types for compatibility
      switch (channelInfo.type) {
        case 'thread':
          channelType = 11; // Map to Discord thread type
          isThreadChannel = true;
          break;
        case 'dm':
          channelType = 1;
          break;
        case 'text':
        default:
          channelType = 0; // Default to text channel
          break;
      }
      
      // Get parent name and ID from ChatChannel interface
      parentName = channelInfo.parentName || null;
      parent_id = channelInfo.parentId || null;
    } else {
      // Fallback for Discord channel info (numeric type)
      channelType = channelInfo.type as number;
      
      // Check if this is a Discord thread using original logic
      isThreadChannel = channelType === 11 || channelType === 12; // PublicThread = 11, PrivateThread = 12
      
      // Get parent name and ID from Discord channel info
      parentName = (channelInfo as any).parent_name || (channelInfo as any).parentName || null;
      parent_id = (channelInfo as any).parent_id || null;
    }
  } else {
    channelType = 0;
  }
  
  const typeName = CHANNEL_TYPE_NAMES[String(channelType)] || `UNKNOWN(${channelType})`;
  log.info(`Channel type: ${channelType} (${typeName}), parent: ${parentName || 'none'}`);

  if (isThreadChannel) {
    log.info(`Detected thread - rejecting (not supported)`);
    return {
      is_project_channel: false,
      workspace_id: null,
      channel_id: message.channel_id,
      channel_name: channelInfo.name || 'unknown',
      channel_type: channelType,
      parent_id: null,
      parent_name: null,
      should_process: false,
    };
  }

  // Check if this channel is in the configured Projects category (case-insensitive)
  const expectedCategory = config.PROJECTS_CATEGORY_NAME.toLowerCase();
  const isInProjectsCategory = parentName
    ? parentName.toLowerCase() === expectedCategory
    : false;

  log.info(
    `Parent category: ${parentName || 'none'}, expected: ${config.PROJECTS_CATEGORY_NAME}, isProjectChannel: ${isInProjectsCategory}`
  );

  return {
    is_project_channel: isInProjectsCategory,
    workspace_id: isInProjectsCategory ? message.channel_id : null,
    channel_id: message.channel_id,
    channel_name: channelInfo.name || 'unknown',
    channel_type: channelType,
    parent_id: parent_id,
    parent_name: parentName,
    should_process: true, // Don't reject messages just for not being in project category
  };
}

export function isGeneralChannel(channelName: string): boolean {
  return channelName.toLowerCase() === 'general';
}
