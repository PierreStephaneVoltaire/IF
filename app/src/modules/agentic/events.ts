import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import { createLogger } from '../../utils/logger';

const log = createLogger('AGENTIC:EVENTS');

const QUEUE_URL = process.env.AGENTIC_EVENTS_QUEUE_URL;

export type AgenticEvent =
  | { type: 'execution_started'; channelId: string; taskType: string; agentRole: string; }
  | { type: 'turn_completed'; channelId: string; turn: number; confidence: number; status: string; }
  | { type: 'model_escalated'; channelId: string; from: string; to: string; reason: string; }
  | { type: 'execution_completed'; channelId: string; totalTurns: number; finalStatus: string; }
  | { type: 'execution_aborted'; channelId: string; reason: 'user_stop' | 'max_turns' | 'stuck'; }
  | { type: 'commit_created'; channelId: string; branch: string; commitHash: string; }
  | { type: 'branch_merged'; channelId: string; branch: string; }
  | { type: 'branch_rejected'; channelId: string; branch: string; };

let sqsClient: SQSClient | null = null;

function getSqsClient(): SQSClient {
  if (!sqsClient) {
    sqsClient = new SQSClient({});
  }
  return sqsClient;
}

/**
 * Emits an event to the SQS queue for external observability
 */
export async function emitEvent(event: AgenticEvent): Promise<void> {
  if (!QUEUE_URL) {
    log.debug('AGENTIC_EVENTS_QUEUE_URL not set, skipping event emission');
    return;
  }

  try {
    const client = getSqsClient();

    await client.send(
      new SendMessageCommand({
        QueueUrl: QUEUE_URL,
        MessageBody: JSON.stringify(event),
        MessageAttributes: {
          eventType: {
            DataType: 'String',
            StringValue: event.type,
          },
          channelId: {
            DataType: 'String',
            StringValue: 'channelId' in event ? event.channelId : 'unknown',
          },
        },
      })
    );

    log.debug(`Emitted event: ${event.type} for channel ${'channelId' in event ? event.channelId : 'unknown'}`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    log.error(`Failed to emit event to SQS: ${errorMessage}`);
    // Don't throw - event emission failures shouldn't break execution
  }
}

/**
 * Emits an execution started event
 */
export async function emitExecutionStarted(params: {
  channelId: string;
  taskType: string;
  agentRole: string;
}): Promise<void> {
  await emitEvent({
    type: 'execution_started',
    ...params,
  });
}

/**
 * Emits a turn completed event
 */
export async function emitTurnCompleted(params: {
  channelId: string;
  turn: number;
  confidence: number;
  status: string;
}): Promise<void> {
  await emitEvent({
    type: 'turn_completed',
    ...params,
  });
}

/**
 * Emits a model escalated event
 */
export async function emitModelEscalated(params: {
  channelId: string;
  from: string;
  to: string;
  reason: string;
}): Promise<void> {
  await emitEvent({
    type: 'model_escalated',
    ...params,
  });
}

/**
 * Emits an execution completed event
 */
export async function emitExecutionCompleted(params: {
  channelId: string;
  totalTurns: number;
  finalStatus: string;
}): Promise<void> {
  await emitEvent({
    type: 'execution_completed',
    ...params,
  });
}

/**
 * Emits an execution aborted event
 */
export async function emitExecutionAborted(params: {
  channelId: string;
  reason: 'user_stop' | 'max_turns' | 'stuck';
}): Promise<void> {
  await emitEvent({
    type: 'execution_aborted',
    ...params,
  });
}

/**
 * Emits a commit created event
 */
export async function emitCommitCreated(params: {
  channelId: string;
  branch: string;
  commitHash: string;
}): Promise<void> {
  await emitEvent({
    type: 'commit_created',
    ...params,
  });
}

/**
 * Emits a branch merged event
 */
export async function emitBranchMerged(params: {
  channelId: string;
  branch: string;
}): Promise<void> {
  await emitEvent({
    type: 'branch_merged',
    ...params,
  });
}

/**
 * Emits a branch rejected event
 */
export async function emitBranchRejected(params: {
  channelId: string;
  branch: string;
}): Promise<void> {
  await emitEvent({
    type: 'branch_rejected',
    ...params,
  });
}
