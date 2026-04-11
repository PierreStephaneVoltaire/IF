import { GetCommand, QueryCommand, PutCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import crypto from 'crypto'
import { docClient, TABLE } from '../db/dynamo'
import { transformProgram } from '../db/transforms'
import { AppError } from '../middleware/errorHandler'
import type { Program, ProgramListItem, Phase, Session, PlannedExercise } from '@powerlifting/types'

const PK = 'operator'

/**
 * Resolve a version string to the actual SK.
 * If version is "current", look up the pointer to get the real version.
 */
async function resolveVersionSk(version: string): Promise<string> {
  if (version === 'current') {
    // Look up the pointer
    const pointerCommand = new GetCommand({
      TableName: TABLE,
      Key: {
        pk: PK,
        sk: 'program#current',
      },
    })

    const pointerResult = await docClient.send(pointerCommand)

    if (!pointerResult.Item) {
      // No pointer exists, fall back to v001
      return 'program#v001'
    }

    // Return the referenced SK
    return (pointerResult.Item as any).ref_sk || 'program#v001'
  }

  return `program#${version}`
}

/**
 * Get a specific program version
 */
export async function getProgram(version: string): Promise<Program> {
  const sk = await resolveVersionSk(version)

  const command = new GetCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk,
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
  })

  const result = await docClient.send(command)

  // Find the current pointer
  const pointer = (result.Items || []).find((item: any) => item.sk === 'program#current')
  const currentRefSk = pointer?.ref_sk || 'program#v001'

  // Filter to only actual programs (not pointers) and map to list items
  const programs = (result.Items || [])
    .filter((item: any) => item.sk !== 'program#current' && item.meta)
    .map((item: any) => ({
      version: item.sk.replace('program#', ''),
      sk: item.sk,
      comp_date: item.meta?.comp_date || '',
      updated_at: item.meta?.updated_at || '',
      version_label: item.meta?.version_label || item.sk.replace('program#', ''),
      is_current: item.sk === currentRefSk,
    }))

  // Add "current" as the first option if there's a pointer
  if (pointer) {
    const currentProgram = programs.find(p => p.is_current)
    programs.unshift({
      version: 'current',
      sk: currentRefSk,
      comp_date: currentProgram?.comp_date || '',
      updated_at: currentProgram?.updated_at || '',
      version_label: currentProgram?.version_label ? `Current (${currentProgram.version_label})` : 'Current',
      is_current: true,
    })
  }

  return programs
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
    'attempt_pct',
  ]

  if (!allowedFields.includes(field)) {
    throw new AppError(`Cannot update field: ${field}`, 400)
  }

  const sk = await resolveVersionSk(version)

  const command = new UpdateCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk,
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
  const sk = await resolveVersionSk(version)

  const command = new UpdateCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk,
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
  const sk = await resolveVersionSk(version)

  const command = new UpdateCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk,
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

/**
 * Batch create planned sessions for a week.
 * Creates one session per day entry, all with status "planned" and the same planned_exercises.
 */
export async function batchCreateWeek(
  version: string,
  weekNumber: number,
  weekLabel: string,
  days: Array<{ date: string; day: string }>,
  phaseName: string,
  exercises: PlannedExercise[]
): Promise<void> {
  const sk = await resolveVersionSk(version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    ProjectionExpression: 'sessions, phases',
  })

  const result = await docClient.send(getCommand)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]
  const phases = (result.Item.phases ?? []) as Phase[]

  const phase = phases.find(p => weekNumber >= p.start_week && weekNumber <= p.end_week)
    ?? { name: phaseName, intent: '', start_week: weekNumber, end_week: weekNumber }

  const existingDates = new Set(sessions.map(s => s.date))
  for (const day of days) {
    if (existingDates.has(day.date)) {
      throw new AppError(`Session with date ${day.date} already exists`, 400)
    }
  }

  const newSessions: Session[] = days.map(day => ({
    id: crypto.randomUUID(),
    date: day.date,
    day: day.day,
    week: weekLabel,
    week_number: weekNumber,
    phase,
    status: 'planned',
    completed: false,
    planned_exercises: exercises,
    exercises: [],
    session_notes: '',
    session_rpe: null,
    body_weight_kg: null,
    block: 'current',
  }))

  sessions.push(...newSessions)
  sessions.sort((a, b) => a.date.localeCompare(b.date))

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET sessions = :sessions, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':sessions': sessions,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}

/**
 * Update planned exercises on a session.
 */
export async function updatePlannedExercises(
  version: string,
  date: string,
  index: number,
  plannedExercises: PlannedExercise[]
): Promise<void> {
  const sk = await resolveVersionSk(version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    ProjectionExpression: 'sessions',
  })

  const result = await docClient.send(getCommand)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]

  if (index < 0 || index >= sessions.length) {
    throw new AppError(`Session at index ${index} not found`, 404)
  }
  if (sessions[index].date !== date) {
    throw new AppError(`Session at index ${index} has date ${sessions[index].date}, expected ${date}`, 409)
  }

  // Sync exercises from planned for incomplete sessions
  const existing = sessions[index]
  const syncExercises = !existing.completed
    ? plannedExercises.map(pe => ({
        name: pe.name,
        sets: pe.sets,
        reps: pe.reps,
        kg: pe.kg,
        notes: '',
        failed_sets: Array(pe.sets).fill(false),
      }))
    : existing.exercises

  sessions[index] = {
    ...existing,
    planned_exercises: plannedExercises,
    ...(syncExercises !== existing.exercises ? { exercises: syncExercises } : {}),
  }

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET sessions = :sessions, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':sessions': sessions,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}
