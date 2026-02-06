import { getConfig } from '../config/index';
import { createLogger } from '../utils/logger';
import type { DiscordMessagePayload } from '../modules/discord/types';
import type { FilterResult } from './types';

const log = createLogger('FILTER');

export function filterMessage(message: DiscordMessagePayload): FilterResult {
  log.info(`Checking message ${message.id}`);

  const config = getConfig();

  const authorUsername = message.author.username.toLowerCase();
  const isSelf = authorUsername === config.BOT_USERNAME.toLowerCase();
  log.info(`Author: ${message.author.username}, is_self: ${isSelf}`);

  if (isSelf) {
    log.info(`Filter result: passed=false, reason=self_message`);
    return {
      passed: false,
      reason: 'Message from self',
      context: {
        is_self: true,
        is_stale: false,
        is_mentioned: false,
        force_respond: false,
        is_breakglass: false,
      },
    };
  }

  const messageTime = new Date(message.timestamp);
  const now = new Date();
  const diffMinutes = (now.getTime() - messageTime.getTime()) / (1000 * 60);
  const isStale = diffMinutes > config.STALENESS_MINUTES;
  log.info(`Message age: ${diffMinutes.toFixed(1)} minutes, is_stale: ${isStale}`);

  if (isStale) {
    log.info(`Filter result: passed=false, reason=stale_message`);
    return {
      passed: false,
      reason: `Message too old (${diffMinutes.toFixed(0)} minutes)`,
      context: {
        is_self: false,
        is_stale: true,
        is_mentioned: false,
        force_respond: false,
        is_breakglass: false,
      },
    };
  }

  // Get the appropriate bot ID based on platform
  const botId = config.CHAT_PLATFORM === 'stoat' && config.STOAT_BOT_ID
    ? config.STOAT_BOT_ID
    : config.DISCORD_BOT_ID;
  
  const isMentioned = checkMention(message, botId);
  log.info(`Mentions bot: ${isMentioned}`);

  // Check for breakglass pattern: @{modelname} at start of message
  const breakglassMatch = message.content.match(/^@(opus|sonnet|gemini|qwen|gpt|default|glm)\b/i);
  const isBreakglass = breakglassMatch !== null;
  const breakglassModel = isBreakglass ? breakglassMatch[1].toLowerCase() : undefined;
  
  if (isBreakglass) {
    log.info(`Breakglass detected: model=${breakglassModel}`);
  }

  const forceRespond = isMentioned || isBreakglass;

  log.info(`Filter result: passed=true`);

  return {
    passed: true,
    context: {
      is_self: false,
      is_stale: false,
      is_mentioned: isMentioned,
      force_respond: forceRespond,
      is_breakglass: isBreakglass,
      breakglass_model: breakglassModel,
    },
  };
}

function checkMention(message: DiscordMessagePayload, botId: string): boolean {
  const hasMention = message.mentions.some((m) => m.id === botId);
  if (hasMention) return true;

  const content = message.content.toLowerCase();
  if (content.includes(`<@${botId}>`) || content.includes(`<@!${botId}>`)) {
    return true;
  }

  const config = getConfig();
  if (content.includes(`@${config.BOT_USERNAME.toLowerCase()}`)) {
    return true;
  }

  return false;
}
