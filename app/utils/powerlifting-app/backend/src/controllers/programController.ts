import { GetCommand, QueryCommand, PutCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { transformProgram } from '../db/transforms'
import { AppError } from '../middleware/errorHandler'
import type { Program, ProgramListItem, Phase } from '@powerlifting/types'

const PK = 'operator'

/**
 * Get a specific program version
 */
export async function getProgram(version: string): Promise<Program> {
  const command = new GetCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: `program#${version}`,
    },
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  return transformProgram(result.Item as Record<string, unknown>)
}

/**
 * List all program versions
 */
export async function listPrograms(): Promise<ProgramListItem[]> {
  const command = new QueryCommand({
    TableName: TABLE,
    KeyConditionExpression: 'pk = :pk AND begins_with(sk, :prefix)',
    ExpressionAttributeValues: {
      ':pk': PK,
      ':prefix': 'program#',
    },
    ProjectionExpression: 'sk, #meta.program_name, #meta.comp_date, #meta.updated_at, #meta.version_label',
    ExpressionAttributeNames: {
      '#meta': 'meta',
    },
  })

  const result = await docClient.send(command)

  return (result.Items || []).map((item: any) => ({
    version: item.sk.replace('program#', ''),
    sk: item.sk,
    comp_date: item.meta?.comp_date || '',
    updated_at: item.meta?.updated_at || '',
    version_label: item.meta?.version_label || '',
  }))
}

/**
 * Fork a program to a new version
 */
export async function forkProgram(
  currentVersion: string,
  label?: string
): Promise<string> {
  // Get current program
  const current = await getProgram(currentVersion)

  // Find next version number
  const all = await listPrograms()
  const nums = all.map(v => parseInt(v.version.replace(/\D/g, ''), 10)).filter(n => !isNaN(n))
  const next = nums.length > 0 ? Math.max(...nums) + 1 : 1
  const newVersion = `v${String(next).padStart(3, '0')}`

  // Clone with updated metadata
  const forked: Program = {
    ...current,
    sk: `program#${newVersion}`,
    meta: {
      ...current.meta,
      version_label: label || newVersion,
      updated_at: new Date().toISOString(),
      change_log: [
        ...current.meta.change_log,
        {
          action: 'forked_from',
          source: currentVersion,
          date: new Date().toISOString(),
        },
      ],
    },
  }

  // Write new item
  const command = new PutCommand({
    TableName: TABLE,
    Item: forked,
  })

  await docClient.send(command)
  return newVersion
}

/**
 * Update a single meta field
 */
export async function updateMetaField(
  version: string,
  field: string,
  value: unknown
): Promise<void> {
  const allowedFields = [
    'program_name', 'program_start', 'comp_date', 'federation', 'practicing_for',
    'version_label', 'weight_class_kg', 'weight_class_confirm_by',
    'current_body_weight_kg', 'current_body_weight_lb',
    'target_squat_kg', 'target_bench_kg', 'target_dl_kg', 'target_total_kg',
  ]

  if (!allowedFields.includes(field)) {
    throw new AppError(`Cannot update field: ${field}`, 400)
  }

  const command = new UpdateCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: `program#${version}`,
    },
    UpdateExpression: `SET #meta.#field = :value, #meta.updated_at = :now`,
    ExpressionAttributeNames: {
      '#meta': 'meta',
      '#field': field,
    },
    ExpressionAttributeValues: {
      ':value': value,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(command)
}

/**
 * Update body weight
 */
export async function updateBodyWeight(
  version: string,
  weightKg: number
): Promise<void> {
  const weightLb = weightKg * 2.20462

  const command = new UpdateCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: `program#${version}`,
    },
    UpdateExpression: `SET #meta.current_body_weight_kg = :kg, #meta.current_body_weight_lb = :lb, #meta.updated_at = :now`,
    ExpressionAttributeNames: {
      '#meta': 'meta',
    },
    ExpressionAttributeValues: {
      ':kg': weightKg,
      ':lb': weightLb,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(command)
}

/**
 * Update phases
 */
export async function updatePhases(
  version: string,
  phases: Phase[]
): Promise<void> {
  const command = new UpdateCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: `program#${version}`,
    },
    UpdateExpression: `SET phases = :phases, #meta.updated_at = :now`,
    ExpressionAttributeNames: {
      '#meta': 'meta',
    },
    ExpressionAttributeValues: {
      ':phases': phases,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(command)
}
