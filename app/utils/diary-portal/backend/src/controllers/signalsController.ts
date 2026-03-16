import { GetCommand, QueryCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, SIGNALS_TABLE, OPERATOR_PK } from '../db/dynamodb'
import { countActiveEntries } from './entriesController'
import type { DiarySignal } from '@diary-portal/types'

/**
 * Get the latest signal (signal#latest)
 * This is the current mental health snapshot
 */
export async function getLatestSignal(): Promise<DiarySignal | null> {
  const command = new GetCommand({
    TableName: SIGNALS_TABLE,
    Key: {
      pk: OPERATOR_PK,
      sk: 'signal#latest',
    },
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    return null
  }

  return result.Item as DiarySignal
}

/**
 * Get signal history for charting
 * Returns all signals except signal#latest, filtered by date range
 * Sorted by computed_at ascending for charting
 */
export async function getSignalHistory(days: number = 90): Promise<DiarySignal[]> {
  const cutoffDate = new Date()
  cutoffDate.setDate(cutoffDate.getDate() - days)
  const cutoffISO = cutoffDate.toISOString()

  const command = new QueryCommand({
    TableName: SIGNALS_TABLE,
    KeyConditionExpression: 'pk = :pk AND begins_with(sk, :sk_prefix)',
    FilterExpression: 'computed_at >= :cutoff',
    ExpressionAttributeValues: {
      ':pk': OPERATOR_PK,
      ':sk_prefix': 'signal#',
      ':cutoff': cutoffISO,
    },
  })

  const result = await docClient.send(command)

  if (!result.Items) {
    return []
  }

  // Filter out signal#latest in code (can't filter on primary key in DynamoDB)
  const signals = result.Items
    .filter(item => item.sk !== 'signal#latest') as DiarySignal[]

  // Sort by computed_at ascending for charting
  return signals.sort((a, b) => a.computed_at.localeCompare(b.computed_at))
}

/**
 * Get active entry count
 * Reuses entriesController function
 */
export async function getEntryCount(): Promise<number> {
  return countActiveEntries()
}
