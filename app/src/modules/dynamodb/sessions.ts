import { GetCommand, PutCommand, UpdateCommand, DeleteCommand } from '@aws-sdk/lib-dynamodb';
import { getDynamoDBClient } from './index';
import { getConfig } from '../../config/index';
import { createLogger } from '../../utils/logger';
import type { Session, SessionUpdate } from './types';

const log = createLogger('DYNAMODB:SESSIONS');

export async function getSession(channelid: string): Promise<Session | null> {
  log.info(`getSession: ${channelid}`);

  const client = getDynamoDBClient();
  const config = getConfig();

  const startTime = Date.now();
  const result = await client.send(
    new GetCommand({
      TableName: config.DYNAMODB_SESSIONS_TABLE,
      Key: { channel_id: channelid },
    })
  );
  const elapsedMs = Date.now() - startTime;
  log.info(`⏱️ DynamoDB getSession completed in ${elapsedMs}ms`);

  const exists = !!result.Item;
  log.info(`Session found: ${exists}`);

  if (!result.Item) {
    return null;
  }

  return result.Item as Session;
}

export async function createSession(session: Session): Promise<void> {
  log.info(`createSession: ${session.channel_id}`);

  const client = getDynamoDBClient();
  const config = getConfig();

  const startTime = Date.now();
  await client.send(
    new PutCommand({
      TableName: config.DYNAMODB_SESSIONS_TABLE,
      Item: session,
    })
  );
  const elapsedMs = Date.now() - startTime;
  log.info(`⏱️ DynamoDB createSession completed in ${elapsedMs}ms`);

  log.info(`Session created successfully: ${session.channel_id}`);
}

export async function updateSession(channelid: string, updates: SessionUpdate): Promise<void> {
  log.info(`updateSession: ${channelid}`, { fields: Object.keys(updates) });

  const client = getDynamoDBClient();
  const config = getConfig();

  const updateExpressions: string[] = [];
  const expressionAttributeNames: Record<string, string> = {};
  const expressionAttributeValues: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(updates)) {
    if (value !== undefined) {
      updateExpressions.push(`#${key} = :${key}`);
      expressionAttributeNames[`#${key}`] = key;
      expressionAttributeValues[`:${key}`] = value;
    }
  }

  if (updateExpressions.length === 0) {
    log.info('No fields to update');
    return;
  }

  const startTime = Date.now();
  await client.send(
    new UpdateCommand({
      TableName: config.DYNAMODB_SESSIONS_TABLE,
      Key: { channel_id: channelid },
      UpdateExpression: `SET ${updateExpressions.join(', ')}`,
      ExpressionAttributeNames: expressionAttributeNames,
      ExpressionAttributeValues: expressionAttributeValues,
    })
  );
  const elapsedMs = Date.now() - startTime;
  log.info(`⏱️ DynamoDB updateSession completed in ${elapsedMs}ms`);

  log.info(`Session updated successfully: ${channelid}`);
}

export async function getOrCreateSession(channelid: string, branchName: string): Promise<Session> {
  log.info(`getOrCreateSession: ${channelid}`);

  let session = await getSession(channelid);

  if (!session) {
    log.info(`Session not found, creating new session`);
    session = {
      channel_id: channelid,
      branch_name: branchName,
      topic_summary: '',
      has_progress: false,
      confidence_score: 80, // Default to 80 as per initial requirement
      last_discord_timestamp: new Date().toISOString(),
      last_message: '',
      created_at: new Date().toISOString(),
      sub_topics: {},
      workspace_path: `/workspace/${channelid}`,
      s3_prefix: `s3://discord-bot-artifacts/threads/${channelid}/`,
      synced_files: [],
    };

    await createSession(session);
  }

  return session;
}

export async function updateSessionConfidence(
  channelid: string,
  adjustment: number
): Promise<void> {
  const session = await getSession(channelid);
  if (!session) return;

  const currentScore = session.confidence_score || 50;
  const newScore = Math.min(100, Math.max(10, currentScore + adjustment));

  log.info(`Updating confidence for thread ${channelid}: ${currentScore} -> ${newScore} (adj: ${adjustment})`);

  await updateSession(channelid, { confidence_score: newScore });
}

export async function deleteSession(channelid: string): Promise<void> {
  log.info(`Deleting session from DynamoDB: ${channelid}`);
  const client = getDynamoDBClient();
  const config = getConfig();

  const startTime = Date.now();
  await client.send(new DeleteCommand({
    TableName: config.DYNAMODB_SESSIONS_TABLE,
    Key: { channel_id: channelid },
  }));
  const elapsedMs = Date.now() - startTime;
  log.info(`⏱️ DynamoDB deleteSession completed in ${elapsedMs}ms`);
}
