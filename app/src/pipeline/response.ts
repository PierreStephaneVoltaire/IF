import { getDiscordClient, sendMessage, sendMessageChunks } from '../modules/discord/index';
import { getChatClient } from '../modules/chat';
import { createLogger } from '../utils/logger';
import { parseResponse } from '../modules/workspace/response-parser';
import { workspaceManager } from '../modules/workspace/manager';

const log = createLogger('RESPONSE');

const MAX_DISCORD_LENGTH = 1900;

export interface ResponseInput {
  response: string;
  channelId: string;
  workspaceId: string; // Required for workspace access
}

export async function formatAndSendResponse(input: ResponseInput): Promise<void> {
  log.info(`Formatting response (Workspace: ${input.workspaceId})`);
  log.info(`Raw response length: ${input.response.length}`);
  log.info(`First 200 chars: ${input.response.substring(0, 200)}`);

  const parts = parseResponse(input.response);
  const fileParts = parts.filter(p => p.type === 'file').length;
  const textParts = parts.filter(p => p.type === 'text').length;
  log.info(`Parsed response into ${parts.length} parts (${fileParts} file(s), ${textParts} text)`);

  if (fileParts > 0) {
    log.info(`File markers detected:`);
    parts.filter(p => p.type === 'file').forEach((p, i) => {
      log.info(`  [${i + 1}] ${p.filePath}`);
    });
  }

  log.info(`Sending response to channel ${input.channelId}`);
  const chatClient = getChatClient();
  // Only get Discord client if we're NOT using a non-Discord chat client
  const client = chatClient ? null : getDiscordClient();

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    log.info(`Processing part ${i + 1}/${parts.length} (Type: ${part.type})`);

    if (part.type === 'text') {
      if (part.content.length > MAX_DISCORD_LENGTH) {
        if (chatClient && chatClient.platform !== 'discord') {
          await chatClient.sendMessageChunks(input.channelId, part.content, MAX_DISCORD_LENGTH);
        } else if (client) {
          await sendMessageChunks(client, input.channelId, part.content, MAX_DISCORD_LENGTH);
        }
      } else if (part.content.trim()) {
        if (chatClient && chatClient.platform !== 'discord') {
          await chatClient.sendMessage(input.channelId, { content: part.content });
        } else if (client) {
          await sendMessage(client, input.channelId, { content: part.content });
        }
      }
    } else if (part.type === 'file' && part.filePath) {
      try {
        log.info(`📎 Attempting to fetch file from workspace`);
        log.info(`  Workspace ID: ${input.workspaceId}`);
        log.info(`  File path: ${part.filePath}`);
        log.info(`  Workspace base: /workspace/${input.workspaceId}`);
        log.info(`  Full expected path: /workspace/${input.workspaceId}/${part.filePath}`);

        const content = await workspaceManager.readFile(input.workspaceId, part.filePath);
        log.info(`✅ File read successful! Size: ${content.length} bytes`);

        if (chatClient && chatClient.platform !== 'discord') {
          await chatClient.sendMessage(input.channelId, {
            content: `📎 **${part.content}**`,
            files: [
              {
                name: part.content,
                data: content,
              },
            ],
          });
        } else if (client) {
          await sendMessage(client, input.channelId, {
            content: `📎 **${part.content}**`,
            files: [
              {
                name: part.content,
                data: content,
              },
            ],
          });
        }
        log.info(`✅ File uploaded to Discord: ${part.content}`);
      } catch (err) {
        log.error(`❌ Failed to attach file ${part.filePath}`);
        log.error(`  Workspace ID: ${input.workspaceId}`);
        log.error(`  Error: ${String(err)}`);
        log.error(`  Stack: ${err instanceof Error ? err.stack : 'N/A'}`);

        if (chatClient && chatClient.platform !== 'discord') {
          await chatClient.sendMessage(input.channelId, {
            content: `⚠️ *Could not attach file \`${part.content}\`. It may not have been created or saved properly.*\n\`\`\`\n${String(err)}\n\`\`\``
          });
        } else if (client) {
          await sendMessage(client, input.channelId, {
            content: `⚠️ *Could not attach file \`${part.content}\`. It may not have been created or saved properly.*\n\`\`\`\n${String(err)}\n\`\`\``
          });
        }
      }
    }

    if (i < parts.length - 1) {
      await sleep(1500); // Respect rate limits
    }
  }

  log.info('All response parts processed');
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
