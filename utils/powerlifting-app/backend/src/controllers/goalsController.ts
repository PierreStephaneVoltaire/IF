import { GetCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { AppError } from '../middleware/errorHandler'
import type { AthleteGoal } from '@powerlifting/types'

async function resolveVersionSk(pk: string, version: string): Promise<string> {
  if (version === 'current') {
    const pointerCommand = new GetCommand({
      TableName: TABLE,
      Key: { pk, sk: 'program#current' },
    })
    const pointerResult = await docClient.send(pointerCommand)
    if (!pointerResult.Item) return 'program#v001'
    return (pointerResult.Item as any).ref_sk || 'program#v001'
  }
  return `program#${version}`
}

export async function getGoals(pk: string, version: string): Promise<AthleteGoal[]> {
  const sk = await resolveVersionSk(pk, version)

  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
    ProjectionExpression: 'goals',
  })

  const result = await docClient.send(getCommand)
  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  return (result.Item.goals ?? []) as AthleteGoal[]
}

export async function updateGoals(
  pk: string,
  version: string,
  goals: AthleteGoal[],
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
    UpdateExpression: 'SET goals = :goals, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':goals': goals,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}
