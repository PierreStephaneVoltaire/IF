/**
 * DynamoDB Checkpointer for LangGraph
 *
 * Implements checkpoint saving/loading for graph execution state.
 * Stores checkpoints with metadata including failed_node, failed_model, error_message.
 *
 * @see plans/langgraph-migration-plan.md §1
 */

import { AttributeValue } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb';
import { getConfig } from '../../config/index';
import { createLogger } from '../../utils/logger';
import type { CheckpointMetadata } from './state';
import { deserializeState, serializeState, type GraphState } from './state';

const log = createLogger('CHECKPOINTER');

// ---------------------------------------------------------------------------
// Types (LangGraph-compatible)
// ---------------------------------------------------------------------------

export interface CheckpointTuple {
  thread_id: string;
  checkpoint_id: string;
}

export interface CheckpointBundle {
  checkpoint: GraphState;
  metadata: CheckpointMetadata;
}

export interface ListOptions {
  limit?: number;
  before?: string;
  offset?: number;
}

export interface CheckpointListResult {
  checkpoints: CheckpointBundle[];
  next_offset?: number;
}

export type CheckpointCursor = string | undefined;

// ---------------------------------------------------------------------------
// DynamoDB Checkpointer
// ---------------------------------------------------------------------------

export class DynamoDBCheckpointer {
  private docClient: DynamoDBDocumentClient;
  private tableName: string;
  private ttlDays: number = 30;

  constructor() {
    const config = getConfig();

    // Use the existing DynamoDB client from dynamodb module
    const { getDynamoDBClient } = require('../dynamodb');
    this.docClient = getDynamoDBClient();

    this.tableName = config.DYNAMODB_SESSIONS_TABLE + '_checkpoints'; // Fallback naming
    if (process.env.LANGGRAPH_CHECKPOINTS_TABLE) {
      this.tableName = process.env.LANGGRAPH_CHECKPOINTS_TABLE;
    }
    log.info(`DynamoDB checkpointer initialized for table: ${this.tableName}`);
  }

  private generateCheckpointId(state: GraphState): string {
    const timestamp = Date.now();
    return `${state.executionId}-${state.turnNumber}-${timestamp}`;
  }

  async put(
    threadId: string,
    checkpointId: string,
    state: GraphState,
    metadata: CheckpointMetadata
  ): Promise<void> {
    const serializedState = serializeState(state);
    const ttl = Math.floor(Date.now() / 1000) + (this.ttlDays * 24 * 60 * 60);

    log.info(`Saving checkpoint: thread=${threadId}, checkpoint=${checkpointId}, turn=${state.turnNumber}`);

    const item: Record<string, AttributeValue> = {
      PK: { S: threadId },
      SK: { S: checkpointId },
      checkpoint: { S: JSON.stringify(serializedState) },
      metadata: { S: JSON.stringify(metadata) },
      ttl: { N: ttl.toString() },
      created_at: { S: new Date().toISOString() },
    };

    const { PutItemCommand } = await import('@aws-sdk/client-dynamodb');
    const command = new PutItemCommand({
      TableName: this.tableName,
      Item: item,
    });

    try {
      await this.docClient.send(command);
      log.info(`Checkpoint saved successfully: ${checkpointId}`);
    } catch (error) {
      log.error(`Failed to save checkpoint: ${checkpointId}`, { error });
      throw error;
    }
  }

  async getTuple(threadId: string, checkpointId: string): Promise<CheckpointBundle | null> {
    const { GetItemCommand } = await import('@aws-sdk/client-dynamodb');
    const command = new GetItemCommand({
      TableName: this.tableName,
      Key: {
        PK: { S: threadId },
        SK: { S: checkpointId },
      },
    });

    try {
      const result = await this.docClient.send(command);

      if (!result.Item) {
        log.debug(`Checkpoint not found: ${checkpointId}`);
        return null;
      }

      const state = JSON.parse(result.Item.checkpoint.S || '{}');
      const meta = JSON.parse(result.Item.metadata.S || '{}') as CheckpointMetadata;

      log.debug(`Checkpoint retrieved: ${checkpointId}`);
      return {
        checkpoint: deserializeState(state),
        metadata: meta,
      };
    } catch (error) {
      log.error(`Failed to get checkpoint: ${checkpointId}`, { error });
      throw error;
    }
  }

  async list(
    threadId: string,
    options: ListOptions = {}
  ): Promise<CheckpointListResult> {
    const { limit = 100, before } = options;

    const { QueryCommand } = await import('@aws-sdk/client-dynamodb');
    const command = new QueryCommand({
      TableName: this.tableName,
      KeyConditionExpression: 'PK = :pk',
      ExpressionAttributeValues: {
        ':pk': { S: threadId },
      },
      ScanIndexForward: false,
      Limit: limit,
      ExclusiveStartKey: before
        ? { PK: { S: threadId }, SK: { S: before } }
        : undefined,
    });

    try {
      const result = await this.docClient.send(command);

      const checkpoints: CheckpointBundle[] = (result.Items || []).map((item) => ({
        checkpoint: deserializeState(JSON.parse(item.checkpoint.S || '{}')),
        metadata: JSON.parse(item.metadata.S || '{}') as CheckpointMetadata,
      }));

      log.debug(`Listed ${checkpoints.length} checkpoints for thread: ${threadId}`);

      const lastKey = result.LastEvaluatedKey;
      let nextOffset: number | undefined;
      if (lastKey && lastKey.SK?.S) {
        const parts = lastKey.SK.S.split('-');
        nextOffset = parseInt(parts[parts.length - 1] || '0', 10);
      }

      return {
        checkpoints,
        next_offset: nextOffset,
      };
    } catch (error) {
      log.error(`Failed to list checkpoints for thread: ${threadId}`, { error });
      throw error;
    }
  }

  async getLatest(threadId: string): Promise<CheckpointBundle | null> {
    const result = await this.list(threadId, { limit: 1 });
    return result.checkpoints[0] || null;
  }

  async delete(threadId: string, checkpointId: string): Promise<void> {
    const { DeleteItemCommand } = await import('@aws-sdk/client-dynamodb');
    const command = new DeleteItemCommand({
      TableName: this.tableName,
      Key: {
        PK: { S: threadId },
        SK: { S: checkpointId },
      },
    });

    try {
      await this.docClient.send(command);
      log.info(`Checkpoint deleted: ${checkpointId}`);
    } catch (error) {
      log.error(`Failed to delete checkpoint: ${checkpointId}`, { error });
      throw error;
    }
  }

  async saveWithFailure(
    state: GraphState,
    failedNode: string,
    failedModel: string,
    errorMessage: string,
    provider: string,
    errorType: 'timeout' | 'rate_limit' | 'api_error' | 'tool_error' | 'unknown' = 'unknown'
  ): Promise<void> {
    const checkpointId = this.generateCheckpointId(state);
    const metadata: CheckpointMetadata = {
      failed_node: failedNode,
      failed_model: failedModel,
      error_message: errorMessage,
      error_type: errorType,
      provider,
      created_at: new Date().toISOString(),
    };

    await this.put(state.channelId, checkpointId, state, metadata);
  }
}

// ---------------------------------------------------------------------------
// Singleton instance
// ---------------------------------------------------------------------------

let checkpointer: DynamoDBCheckpointer | null = null;

export function getCheckpointer(): DynamoDBCheckpointer {
  if (!checkpointer) {
    checkpointer = new DynamoDBCheckpointer();
  }
  return checkpointer;
}
