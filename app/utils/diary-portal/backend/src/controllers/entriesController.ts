import { PutCommand, QueryCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, ENTRIES_TABLE, OPERATOR_PK } from '../db/dynamodb'
import type { DiaryEntry } from '@diary-portal/types'

// TTL: 3 days in seconds
const TTL_SECONDS = 259200

/**
 * Write a new diary entry with TTL
 * Entry is write-only - this is the only function that creates entries
 */
export async function writeEntry(content: string): Promise<void> {
  const now = new Date()
  const isoTimestamp = now.toISOString()
  const expiresAt = Math.floor(now.getTime() / 1000) + TTL_SECONDS

  const entry: DiaryEntry = {
    pk: OPERATOR_PK,
    sk: `entry#${isoTimestamp}`,
    content,
    created_at: isoTimestamp,
    expires_at: expiresAt,
  }

  const command = new PutCommand({
    TableName: ENTRIES_TABLE,
    Item: entry,
  })

  await docClient.send(command)
}

/**
 * Count active (non-expired) entries
 * Used to show the user how much data the agent has to work with
 * Returns count only - never returns entry content
 */
export async function countActiveEntries(): Promise<number> {
  const now = Math.floor(Date.now() / 1000)

  const command = new QueryCommand({
    TableName: ENTRIES_TABLE,
    KeyConditionExpression: 'pk = :pk AND begins_with(sk, :sk_prefix)',
    FilterExpression: 'expires_at > :now',
    ExpressionAttributeValues: {
      ':pk': OPERATOR_PK,
      ':sk_prefix': 'entry#',
      ':now': now,
    },
    Select: 'COUNT',
  })

  const result = await docClient.send(command)
  return result.Count || 0
}
