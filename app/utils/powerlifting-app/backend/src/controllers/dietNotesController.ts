import { GetCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { AppError } from '../middleware/errorHandler'
import type { DietNote } from '@powerlifting/types'

const PK = 'operator'

/**
 * Resolve a version string to the actual SK.
 */
async function resolveVersionSk(version: string): Promise<string> {
  if (version === 'current') {
    const pointerCommand = new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: 'program#current' },
    })
    const pointerResult = await docClient.send(pointerCommand)
    if (!pointerResult.Item) return 'program#v001'
    return (pointerResult.Item as any).ref_sk || 'program#v001'
  }
  return `program#${version}`
}

/**
 * Update all diet notes
 */
export async function updateDietNotes(
  version: string,
  dietNotes: DietNote[]
): Promise<void> {
  const sk = await resolveVersionSk(version)

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET diet_notes = :notes, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':notes': dietNotes,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}

/**
 * Get diet notes
 */
export async function getDietNotes(version: string): Promise<DietNote[]> {
  const sk = await resolveVersionSk(version)

  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    ProjectionExpression: 'diet_notes',
  })

  const result = await docClient.send(getCommand)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  return (result.Item.diet_notes ?? []) as DietNote[]
}
