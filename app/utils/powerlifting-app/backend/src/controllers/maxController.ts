import { GetCommand, UpdateCommand, PutCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { AppError } from '../middleware/errorHandler'
import type { MaxEntry, MaxHistoryStore } from '@powerlifting/types'

const PK = 'operator'

/**
 * Get max history for a program version
 */
export async function getMaxHistory(version: string): Promise<MaxHistoryStore> {
  const command = new GetCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: `max_history#${version}`,
    },
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    // Return empty history if not found
    return {
      pk: PK,
      sk: `max_history#${version}`,
      entries: [],
      updated_at: new Date().toISOString(),
    }
  }

  return result.Item as MaxHistoryStore
}

/**
 * Add a new max entry to history
 */
export async function addMaxEntry(version: string, entry: MaxEntry): Promise<void> {
  const history = await getMaxHistory(version)

  history.entries.push(entry)
  history.entries.sort((a, b) => b.date.localeCompare(a.date)) // Sort descending by date
  history.updated_at = new Date().toISOString()

  const command = new PutCommand({
    TableName: TABLE,
    Item: history,
  })

  await docClient.send(command)
}

/**
 * Update target maxes in program meta
 */
export async function updateTargetMaxes(
  version: string,
  maxes: { squat_kg: number; bench_kg: number; deadlift_kg: number }
): Promise<void> {
  const command = new UpdateCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: `program#${version}`,
    },
    UpdateExpression: `SET
      #meta.target_squat_kg = :squat,
      #meta.target_bench_kg = :bench,
      #meta.target_dl_kg = :dl,
      #meta.target_total_kg = :total,
      #meta.updated_at = :now`,
    ExpressionAttributeNames: {
      '#meta': 'meta',
    },
    ExpressionAttributeValues: {
      ':squat': maxes.squat_kg,
      ':bench': maxes.bench_kg,
      ':dl': maxes.deadlift_kg,
      ':total': maxes.squat_kg + maxes.bench_kg + maxes.deadlift_kg,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(command)
}

/**
 * Get current target maxes from program meta
 */
export async function getTargetMaxes(version: string): Promise<{
  squat_kg: number
  bench_kg: number
  deadlift_kg: number
  total_kg: number
}> {
  const command = new GetCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: `program#${version}`,
    },
    ProjectionExpression: '#meta.target_squat_kg, #meta.target_bench_kg, #meta.target_dl_kg, #meta.target_total_kg',
    ExpressionAttributeNames: {
      '#meta': 'meta',
    },
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const meta = result.Item.meta as any
  return {
    squat_kg: meta.target_squat_kg,
    bench_kg: meta.target_bench_kg,
    deadlift_kg: meta.target_dl_kg,
    total_kg: meta.target_total_kg,
  }
}
