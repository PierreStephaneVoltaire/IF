import { getConfig } from '../config/index';
import { getDiscordClient, getMessages } from '../modules/discord/index';
import { getChatClient } from '../modules/chat';
import type { ChatMessage } from '../modules/chat/types';
import { createLogger } from '../utils/logger';
import type { DiscordMessagePayload, DiscordAttachment } from '../modules/discord/types';
import type { PollHistoryEntry } from '../modules/dynamodb/types';
import type { FormattedHistory, AttachmentCategory, ChannelContext } from './types';

const log = createLogger('HISTORY');

const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp'];
const TEXT_EXTENSIONS = [
  'js', 'ts', 'py', 'tf', 'txt', 'csv', 'json', 'yaml', 'yml', 'md', 'sh',
  'sql', 'html', 'css', 'xml', 'toml', 'ini', 'go', 'rs', 'java', 'hcl',
];

export async function formatHistory(
  currentMessage: DiscordMessagePayload,
  channel: ChannelContext
): Promise<FormattedHistory> {
  log.info(`Formatting history for channel ${channel.channel_id}`);

  const config = getConfig();
  const chatClient = getChatClient();
  // Only get Discord client if we're NOT using a chat client (i.e., we're on Discord)
  const client = chatClient ? null : getDiscordClient();

  const channelId = channel.workspace_id || channel.channel_id;

  // If we're not in a project channel yet (workspace_id is null), don't fetch channel history
  // This prevents context poisoning when creating new channels
  let messages: Awaited<ReturnType<typeof getMessages>> = [];
  if (channel.workspace_id) {
    if (chatClient && chatClient.platform !== 'discord') {
      const chatMessages = await chatClient.getHistory(channelId, 50);
      messages = chatMessages.map(mapChatMessageToDiscordHistory);
      log.info(`Fetched ${messages.length} messages from ${chatClient.platform} channel ${channel.workspace_id}`);
    } else {
      // Only call getMessages if client is not null (we're on Discord)
      if (client) {
        messages = await getMessages(client, channelId, 50);
        log.info(`Fetched ${messages.length} messages from channel ${channel.workspace_id}`);
      } else {
        log.warn('Discord client not available, skipping history fetch');
        messages = [];
      }
    }
  } else {
    log.info('Not in a project channel yet - using empty history for new channel creation');
  }

  const cutoffTime = new Date();
  cutoffTime.setMinutes(cutoffTime.getMinutes() - config.STALENESS_MINUTES);

  const recentMessages = messages.filter((m) => {
    const msgTime = new Date(m.timestamp);
    return msgTime > cutoffTime;
  });
  log.info(`Filtered to last ${config.STALENESS_MINUTES} minutes: ${recentMessages.length} messages`);

  // Filter out status update messages (embeds from the bot that contain progress updates)
  const isStatusUpdateMessage = (msg: typeof recentMessages[0]): boolean => {
    // Skip bot messages that are status updates (turn_start, turn_complete, checkpoint, etc.)
    if (msg.author.bot) {
      // Check embeds for status update patterns
      const embeds = (msg as any).embeds || [];
      for (const embed of embeds) {
        const title = embed.title || '';
        const description = embed.description || '';

        // Status update patterns in embed titles/descriptions
        const statusPatterns = [
          /🤔 Turn \d+\/\d+/,           // turn_start
          /Turn \d+ Complete/,          // turn_complete
          /💾 Checkpoint/,               // checkpoint
          /🏁 Execution Complete/,       // final checkpoint
          /🚀 Model Escalation/,         // escalation
          /💬 Clarification Needed/,     // clarification_request
          /📋 Planning/,                 // planning
          /🤔 Deciding/,                 // should_respond
          /🔍 Reflection Review/,        // reflection
          /💡 Branching/,                // branching
          /✅ Debugging Task Ready/,     // prompt_ready
          /🔧 Executing Tool/,           // tool_execution
        ];

        if (statusPatterns.some(pattern => pattern.test(title) || pattern.test(description))) {
          return true;
        }
      }
    }
    return false;
  };

  const historyMessages = recentMessages
    .filter((m) => m.id !== currentMessage.id && !isStatusUpdateMessage(m))
    .reverse();

  const formattedLines = historyMessages.map((msg) => {
    const author = getAuthorName(msg.author);
    const content = formatContent(msg.content, msg.mentions);
    const attachmentSummary = getAttachmentSummary(msg.attachments);

    return `${author}: ${content}${attachmentSummary}`;
  });

  const formattedHistory = formattedLines.join('\n');
  log.info(`Formatted history length: ${formattedHistory.length} chars`);

  const currentAuthor = getAuthorName(currentMessage.author);
  log.info(`Current message from: ${currentAuthor}`);

  const currentContent = formatContent(currentMessage.content, currentMessage.mentions);
  const currentAttachments = categorizeAttachments(currentMessage.attachments);
  log.info(`Current message attachments: ${currentMessage.attachments.length}`);

  return {
    formatted_history: formattedHistory,
    current_message: currentContent,
    current_author: currentAuthor,
    current_attachments: currentAttachments,
  };
}

function getAuthorName(author: { username: string; global_name?: string }): string {
  return author.global_name || author.username || 'Unknown';
}

function formatContent(
  content: string,
  mentions: Array<{ id: string; username: string }>
): string {
  let formatted = content;

  for (const mention of mentions) {
    const name = mention.username || 'User';
    formatted = formatted.replace(
      new RegExp(`<@!?${mention.id}>`, 'g'),
      `@${name}`
    );
  }

  return formatted;
}

function getAttachmentSummary(
  attachments: Array<{ filename: string; content_type?: string }>
): string {
  if (!attachments || attachments.length === 0) return '';

  const cats = categorizeAttachments(attachments as DiscordAttachment[]);
  const parts: string[] = [];

  if (cats.images.length > 0) {
    parts.push(`[${cats.images.length} image(s)]`);
  }
  if (cats.textFiles.length > 0) {
    const names = cats.textFiles.map((f) => f.filename).join(', ');
    parts.push(`[${cats.textFiles.length} code file(s): ${names}]`);
  }
  if (cats.otherFiles.length > 0) {
    parts.push(`[${cats.otherFiles.length} other file(s)]`);
  }

  return parts.length > 0 ? '\n' + parts.join('\n') : '';
}

function categorizeAttachments(attachments: DiscordAttachment[]): AttachmentCategory {
  const result: AttachmentCategory = {
    images: [],
    textFiles: [],
    otherFiles: [],
  };

  for (const att of attachments) {
    const ext = getExtension(att.filename);
    const contentType = att.content_type || '';

    if (contentType.startsWith('image/') || IMAGE_EXTENSIONS.includes(ext)) {
      result.images.push(att);
    } else if (contentType.startsWith('text/') || TEXT_EXTENSIONS.includes(ext)) {
      result.textFiles.push(att);
    } else {
      result.otherFiles.push(att);
    }
  }

  return result;
}

function getExtension(filename: string): string {
  const parts = filename.toLowerCase().split('.');
  return parts.length > 1 ? parts[parts.length - 1] : '';
}

function mapChatMessageToDiscordHistory(message: ChatMessage): Awaited<ReturnType<typeof getMessages>>[number] {
  return {
    id: message.id,
    content: message.content,
    author: {
      id: message.author.id,
      username: message.author.username,
      bot: message.author.bot,
      global_name: message.author.displayName || undefined,
    },
    attachments: message.attachments.map((att) => ({
      id: att.id,
      filename: att.filename,
      url: att.url,
      content_type: att.contentType,
      size: att.size,
    })),
    timestamp: message.timestamp,
    mentions: message.mentions.map((mention) => ({
      id: mention.id,
      username: mention.username,
    })),
  };
}

/**
 * Format a poll entry for inclusion in history
 */
export function formatPollEntry(entry: PollHistoryEntry): string {
  let formatted = `Bot: ${entry.question}\n\n`;
  
  entry.options.forEach(opt => {
    formatted += `${opt.id}. ${opt.label}\n`;
    formatted += `   ${opt.description}\n`;
  });
  
  formatted += `\n${entry.selectedBy}: ${entry.selectedOption}`;
  
  return formatted;
}

/**
 * Format multiple poll entries for history
 */
export function formatPollEntries(entries: PollHistoryEntry[]): string {
  if (!entries || entries.length === 0) return '';
  
  return entries.map(entry => formatPollEntry(entry)).join('\n\n---\n\n');
}
