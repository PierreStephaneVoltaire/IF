/**
 * Execution Logger for LangGraph
 *
 * Buffers log lines during execution and flushes to S3 as JSON lines file.
 * Each execution gets a structured log file at:
 *   s3://discord-bot-artifacts/executions/{channelId}/{executionId}/execution.log
 *
 * @see plans/langgraph-migration-plan.md §2
 */

import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getConfig } from '../../config/index';
import { createLogger } from '../../utils/logger';
import type { LogEntry } from './state';

const log = createLogger('EXECUTION LOGGER');

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExecutionLoggerOptions {
  channelId: string;
  executionId: string;
  bucket?: string;
}

/**
 * Execution logger that buffers logs and flushes to S3.
 */
export class ExecutionLogger {
  private channelId: string;
  private executionId: string;
  private bucket: string;
  private buffer: LogEntry[];
  private flushed: boolean = false;

  constructor(options: ExecutionLoggerOptions) {
    this.channelId = options.channelId;
    this.executionId = options.executionId;
    const config = getConfig();
    this.bucket = options.bucket || config.S3_ARTIFACT_BUCKET;
    this.buffer = [];
    log.info(`Execution logger initialized: channel=${this.channelId}, execution=${this.executionId}`);
  }

  /**
   * Log a message with level and optional data.
   */
  log(level: LogEntry['level'], node: string, message: string, data?: unknown): void {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      node,
      message,
      data,
    };
    this.buffer.push(entry);
  }

  debug(node: string, message: string, data?: unknown): void {
    this.log('DEBUG', node, message, data);
  }

  info(node: string, message: string, data?: unknown): void {
    this.log('INFO', node, message, data);
  }

  warn(node: string, message: string, data?: unknown): void {
    this.log('WARN', node, message, data);
  }

  error(node: string, message: string, data?: unknown): void {
    this.log('ERROR', node, message, data);
  }

  /**
   * Add a traversed node to the log.
   */
  recordNode(node: string): void {
    this.info('GRAPH', `Entered node: ${node}`, { node });
  }

  /**
   * Get the S3 key for the execution log.
   */
  getLogKey(): string {
    return `executions/${this.channelId}/${this.executionId}/execution.log`;
  }

  /**
   * Flush all buffered logs to S3 as JSON lines.
   */
  async flush(): Promise<void> {
    if (this.flushed) {
      log.warn('Logger already flushed, skipping...');
      return;
    }

    const s3Key = this.getLogKey();
    log.info(`Flushing ${this.buffer.length} log entries to s3://${this.bucket}/${s3Key}`);

    // Convert buffer to JSON lines format
    const logLines = this.buffer.map((entry) => JSON.stringify(entry)).join('\n');

    try {
      const config = getConfig();
      const client = new S3Client({ region: config.AWS_REGION });

      const command = new PutObjectCommand({
        Bucket: this.bucket,
        Key: s3Key,
        Body: logLines,
        ContentType: 'application/x-ndjson',
        Metadata: {
          channel_id: this.channelId,
          execution_id: this.executionId,
          entry_count: this.buffer.length.toString(),
        },
      });

      await client.send(command);
      this.flushed = true;
      log.info(`Execution logs flushed successfully: ${s3Key}`);
    } catch (error) {
      log.error(`Failed to flush execution logs: ${s3Key}`, { error });
      throw error;
    }
  }

  /**
   * Get the buffered logs as JSON lines (for testing/debugging).
   */
  getBuffer(): LogEntry[] {
    return [...this.buffer];
  }

  /**
   * Upload additional artifacts (mermaid diagram, etc.).
   */
  async uploadArtifact(key: string, body: string | Buffer, contentType: string): Promise<void> {
    const fullKey = `executions/${this.channelId}/${this.executionId}/${key}`;
    log.info(`Uploading artifact: s3://${this.bucket}/${fullKey}`);

    try {
      const config = getConfig();
      const client = new S3Client({ region: config.AWS_REGION });

      const command = new PutObjectCommand({
        Bucket: this.bucket,
        Key: fullKey,
        Body: body,
        ContentType: contentType,
      });

      await client.send(command);
      log.info(`Artifact uploaded successfully: ${fullKey}`);
    } catch (error) {
      log.error(`Failed to upload artifact: ${fullKey}`, { error });
      throw error;
    }
  }

  /**
   * Upload the Mermaid diagram.
   */
  async uploadMermaid(mermaidContent: string): Promise<void> {
    await this.uploadArtifact('execution-diagram.mmd', mermaidContent, 'text/plain');
  }

  /**
   * Upload the rendered PNG diagram.
   */
  async uploadDiagramPng(pngBuffer: Buffer): Promise<void> {
    await this.uploadArtifact('execution-diagram.png', pngBuffer, 'image/png');
  }

  /**
   * Upload metadata JSON.
   */
  async uploadMetadata(metadata: Record<string, unknown>): Promise<void> {
    await this.uploadArtifact('metadata.json', JSON.stringify(metadata, null, 2), 'application/json');
  }

  /**
   * Get the S3 URL for the execution.
   */
  getExecutionUrl(): string {
    return `s3://${this.bucket}/executions/${this.channelId}/${this.executionId}/`;
  }
}

// ---------------------------------------------------------------------------
// Singleton management (per execution)
// ---------------------------------------------------------------------------

const activeLoggers: Map<string, ExecutionLogger> = new Map();

export function createExecutionLogger(options: ExecutionLoggerOptions): ExecutionLogger {
  const key = `${options.channelId}:${options.executionId}`;

  // Clean up existing logger for same execution
  const existing = activeLoggers.get(key);
  if (existing) {
    existing.flush().catch(() => {});
    activeLoggers.delete(key);
  }

  const logger = new ExecutionLogger(options);
  activeLoggers.set(key, logger);
  return logger;
}

export function getExecutionLogger(key: string): ExecutionLogger | undefined {
  return activeLoggers.get(key);
}

export async function flushAllLoggers(): Promise<void> {
  const loggers = Array.from(activeLoggers.values());
  await Promise.all(loggers.map((logger) => logger.flush().catch(() => {})));
  activeLoggers.clear();
}
