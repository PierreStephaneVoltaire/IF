/**
 * Stoat Adapter - wraps stoat.js to implement ChatClient interface
 */

// Polyfill WebSocket for stoat.js (it expects a global WebSocket)
import { WebSocket } from 'ws';
(global as unknown as { WebSocket: typeof WebSocket }).WebSocket = WebSocket;

type StoatClient = any;
import type {
  ChatClient,
  ChatMessage,
  ChatReaction,
  SendMessageOptions,
  ChatChannel,
} from '../types';
import { createLogger } from '../../../utils/logger';

const log = createLogger('CHAT:STOAT');

export interface StoatAdapterConfig {
  token: string;
  botId: string;
  baseURL?: string; // e.g., https://stoat.chat/api or https://notdiscord.example.com/api
}

// Type definitions for Stoat.js (since we don't have exact types)
interface StoatMessage {
  id: string;
  channelId: string;
  guildId?: string; // Stoat may have serverId or guildId
  serverId?: string; // Alternative name for guild/server ID
  content: string;
  author: {
    id: string;
    username: string;
    bot: boolean;
  };
  attachments?: Array<{
    id: string;
    filename: string;
    url: string;
    contentType?: string;
    size: number;
  }>;
  mentions?: Array<{
    id: string;
    username: string;
  }>;
  timestamp: string;
  channel: {
    sendMessage: (content: string) => Promise<unknown>;
    guildId?: string; // May be on the channel object
    serverId?: string;
  };
  reply?: {
    channelId: string;
    messageId: string;
  };
}

interface StoatReaction {
  message: {
    id: string;
    channelId: string;
  };
  emoji: {
    name: string;
  };
  userId: string;
}

export class StoatAdapter implements ChatClient {
  public readonly platform = 'stoat' as const;
  public botUserId = '';
  public botUsername = '';
  public isReady = false;

  private client: StoatClient;
  private config: StoatAdapterConfig;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectBaseDelayMs = 1000;
  private messageHandler?: (message: ChatMessage) => Promise<void>;
  private reactionHandler?: (reaction: ChatReaction) => Promise<void>;
  private readyHandler?: () => Promise<void>;
  private threadDeleteHandler?: (channelid: string) => Promise<void>;

  constructor(config: StoatAdapterConfig) {
    this.config = config;
    const StoatClientCtor = (require('stoat.js') as { Client: new (options?: { baseURL?: string }) => StoatClient }).Client;
    // Pass baseURL to the Stoat client constructor if provided
    const clientOptions = config.baseURL ? { baseURL: config.baseURL } : undefined;
    this.client = new StoatClientCtor(clientOptions);
    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    this.client.on('ready', async () => {
      // Stoat client has user property similar to Discord
      const user = (this.client as unknown as { user?: { id: string; username: string } }).user;
      log.info(`Stoat client ready as ${user?.username}`);
      this.botUserId = user?.id || '';
      this.botUsername = user?.username || '';
      this.isReady = true;

      if (this.readyHandler) {
        await this.readyHandler();
      }
    });

    this.client.on('messageCreate', async (message: StoatMessage) => {
      // Skip bot messages
      if (message.author.bot) return;

      if (this.messageHandler) {
        const chatMessage = this.convertMessage(message);
        await this.messageHandler(chatMessage);
      }
    });

    this.client.on('messageReactionAdd', async (reaction: StoatReaction, userId: string) => {
      if (this.reactionHandler) {
        const chatReaction: ChatReaction = {
          messageId: reaction.message.id,
          channelId: reaction.message.channelId,
          emoji: reaction.emoji.name,
          userId: userId,
        };
        await this.reactionHandler(chatReaction);
      }
    });

    // Stoat may have different event names for channel/thread deletion
    // This is a placeholder - adjust based on actual Stoat.js API
    this.client.on('channelDelete', async (channel: { id: string }) => {
      log.info(`Channel deleted: ${channel.id}`);
      if (this.threadDeleteHandler) {
        await this.threadDeleteHandler(channel.id);
      }
    });

    this.client.on('disconnect', async (reason: unknown) => {
      log.warn('Stoat client disconnected', { reason });
      this.isReady = false;
      await this.handleReconnect();
    });

    this.client.on('error', async (error: unknown) => {
      log.error('Stoat client error', { error });
      const errorData = error as { type?: string; data?: { type?: string } };
      if (errorData?.data?.type === 'InvalidSession') {
        log.error('InvalidSession error - STOAT_TOKEN may be invalid or expired');
      }
    });
  }

  private convertMessage(message: StoatMessage): ChatMessage {
    // Try to get guild/server ID from message or channel
    const guildId = message.guildId || message.serverId || message.channel.guildId || message.channel.serverId || null;
    
    return {
      id: message.id,
      channelId: message.channelId,
      guildId: guildId,
      content: message.content,
      author: {
        id: message.author.id,
        username: message.author.username,
        bot: message.author.bot,
        displayName: message.author.username,
      },
      attachments:
        message.attachments?.map((att) => ({
          id: att.id,
          filename: att.filename,
          url: att.url,
          contentType: att.contentType,
          size: att.size,
        })) || [],
      mentions:
        message.mentions?.map((m) => ({
          id: m.id,
          username: m.username,
        })) || [],
      timestamp: message.timestamp,
      replyTo: message.reply,
      // Stoat thread info may differ
      thread: undefined,
    };
  }

  async connect(): Promise<void> {
    log.info('Connecting to Stoat...');

    if (!this.config.token) {
      throw new Error('STOAT_TOKEN is not configured');
    }

    try {
      // Stoat uses loginBot method
      await (this.client as unknown as { loginBot: (token: string) => Promise<void> }).loginBot(
        this.config.token
      );
      log.info('Successfully logged in to Stoat');
    } catch (error) {
      log.error('Failed to connect to Stoat', { error });
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    log.info('Disconnecting from Stoat...');
    this.isReady = false;
    // Stoat client may have different disconnect method
    // Adjust based on actual API
  }

  onMessage(handler: (message: ChatMessage) => Promise<void>): void {
    log.info('Registering message handler for Stoat');
    this.messageHandler = handler;
  }

  onReaction(handler: (reaction: ChatReaction) => Promise<void>): void {
    this.reactionHandler = handler;
  }

  onReady(handler: () => Promise<void>): void {
    this.readyHandler = handler;
  }

  onThreadDelete(handler: (channelid: string) => Promise<void>): void {
    this.threadDeleteHandler = handler;
  }

  async sendMessage(channelId: string, options: SendMessageOptions): Promise<void> {
    // Stoat API may differ - this is based on the example in their README
    // channel.sendMessage(content)

    // We need to get the channel first
    // Stoat client structure may differ from Discord.js
    const channel = await this.getChannel(channelId);
    if (!channel) {
      throw new Error(`Invalid channel: ${channelId}`);
    }

    log.info(`Sending message to Stoat channel ${channelId}: ${options.content.substring(0, 50)}...`);

    const clientAny = this.client as unknown as {
      channels?: {
        fetch?: (id: string) => Promise<{ sendMessage?: (content: string) => Promise<unknown>; send?: (content: string) => Promise<unknown> }>;
        get?: (id: string) => { sendMessage?: (content: string) => Promise<unknown>; send?: (content: string) => Promise<unknown> } | undefined;
      };
    };

    const channelApi = clientAny.channels?.fetch
      ? await clientAny.channels.fetch(channelId)
      : clientAny.channels?.get
        ? clientAny.channels.get(channelId)
        : null;

    if (channelApi?.sendMessage) {
      await channelApi.sendMessage(options.content);
      return;
    }

    if (channelApi?.send) {
      await channelApi.send(options.content);
      return;
    }

    throw new Error('Stoat channel send method not available');
  }

  async sendMessageChunks(channelId: string, content: string, maxLength = 1900): Promise<void> {
    const chunks = this.splitContent(content, maxLength);

    for (let i = 0; i < chunks.length; i++) {
      await this.sendMessage(channelId, { content: chunks[i] });

      if (i < chunks.length - 1) {
        await this.sleep(1500);
      }
    }
  }

  private splitContent(content: string, maxLength: number): string[] {
    const chunks: string[] = [];
    let remaining = content;

    while (remaining.length > 0) {
      if (remaining.length <= maxLength) {
        chunks.push(remaining);
        break;
      }

      let splitIndex = remaining.lastIndexOf('\n', maxLength);
      if (splitIndex === -1 || splitIndex < maxLength * 0.8) {
        splitIndex = remaining.lastIndexOf(' ', maxLength);
      }
      if (splitIndex === -1 || splitIndex < maxLength * 0.8) {
        splitIndex = maxLength;
      }

      chunks.push(remaining.substring(0, splitIndex));
      remaining = remaining.substring(splitIndex).trim();
    }

    return chunks;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private async handleReconnect(): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      log.error(`Max reconnection attempts (${this.maxReconnectAttempts}) reached. Giving up.`);
      return;
    }

    this.reconnectAttempts += 1;
    const delay = this.reconnectBaseDelayMs * Math.pow(2, this.reconnectAttempts - 1);
    log.info(`Attempting Stoat reconnection ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
    await this.sleep(delay);

    try {
      await this.connect();
      this.reconnectAttempts = 0;
    } catch (error) {
      log.error('Stoat reconnection failed', { error });
      await this.handleReconnect();
    }
  }

  async getHistory(channelId: string, limit = 50): Promise<ChatMessage[]> {
    // Stoat API for fetching history may differ
    log.debug(`Fetching history for Stoat channel ${channelId}, limit ${limit}`);

    const clientAny = this.client as unknown as {
      channels?: {
        fetch?: (id: string) => Promise<{ fetchMessages?: (options: { limit: number }) => Promise<StoatMessage[]>; messages?: { fetch?: (options: { limit: number }) => Promise<StoatMessage[]> } }>;
        get?: (id: string) => { fetchMessages?: (options: { limit: number }) => Promise<StoatMessage[]>; messages?: { fetch?: (options: { limit: number }) => Promise<StoatMessage[]> } } | undefined;
      };
    };

    const channelApi = clientAny.channels?.fetch
      ? await clientAny.channels.fetch(channelId)
      : clientAny.channels?.get
        ? clientAny.channels.get(channelId)
        : null;

    if (channelApi?.fetchMessages) {
      const messages = await channelApi.fetchMessages({ limit });
      return messages.map((msg) => this.convertMessage(msg));
    }

    if (channelApi?.messages?.fetch) {
      const messages = await channelApi.messages.fetch({ limit });
      return messages.map((msg) => this.convertMessage(msg));
    }

    return [];
  }

  async addReaction(channelId: string, messageId: string, emoji: string): Promise<void> {
    // Stoat reaction API may differ
    log.debug(`Adding reaction ${emoji} to message ${messageId} in channel ${channelId}`);
  }

  async createThread(channelId: string, messageId: string, name: string): Promise<ChatChannel> {
    throw new Error('createThread is deprecated; use createProjectChannel instead');
  }

  async createProjectChannel(
    guildId: string,
    name: string,
    categoryName: string = 'Projects'
  ): Promise<ChatChannel> {
    log.info(`Creating project channel in Stoat server ${guildId}: ${name}`);
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .split(/\s+/)
      .slice(0, 4)
      .join('-')
      .substring(0, 100) || `project-${Date.now()}`;

    const clientAny = this.client as unknown as {
      servers?: {
        get?: (id: string) => {
          channels?: {
            create?: (options: { name: string; type?: string; parentId?: string }) => Promise<{ id: string; name: string; parentId?: string | null }>;
            find?: (predicate: (channel: { id: string; name?: string; type?: string; parentId?: string | null }) => boolean) => { id: string; name?: string; type?: string; parentId?: string | null } | undefined;
          };
        } | undefined;
      };
    };

    const server = clientAny.servers?.get ? clientAny.servers.get(guildId) : undefined;
    if (!server || !server.channels) {
      throw new Error(`Stoat server not available for guild ${guildId}`);
    }

    const existingCategory = server.channels.find
      ? server.channels.find((channel) => (channel.type === 'category' || channel.type === 'Category')
          && (channel.name || '').toLowerCase() === categoryName.toLowerCase())
      : undefined;

    let categoryId: string | undefined = existingCategory?.id;

    if (!categoryId && server.channels.create) {
      const category = await server.channels.create({
        name: categoryName,
        type: 'category',
      });
      categoryId = category.id;
    }

    if (!server.channels.create) {
      throw new Error('Stoat channel create method not available');
    }

    const created = await server.channels.create({
      name: slug,
      type: 'text',
      parentId: categoryId,
    });

    return {
      id: created.id,
      name: created.name || slug,
      type: 'text',
      parentId: created.parentId || categoryId,
      parentName: categoryName,
    };
  }

  async getChannel(channelId: string): Promise<ChatChannel | null> {
    try {
      // Stoat channel fetching API may differ
      const clientAny = this.client as unknown as {
        channels?: {
          fetch?: (id: string) => Promise<{ id: string; name?: string; type?: string | number; parentId?: string | null }>;
          get?: (id: string) => { id: string; name?: string; type?: string | number; parentId?: string | null } | undefined;
        };
      };

      const channel = clientAny.channels?.fetch
        ? await clientAny.channels.fetch(channelId)
        : clientAny.channels?.get
          ? clientAny.channels.get(channelId)
          : null;

      return {
        id: channel?.id || channelId,
        name: channel?.name || 'unknown',
        type: 'text',
        parentId: channel?.parentId || undefined,
        parentName: undefined,
      };
    } catch (error) {
      log.error(`Failed to fetch Stoat channel ${channelId}`, { error });
      return null;
    }
  }
}
