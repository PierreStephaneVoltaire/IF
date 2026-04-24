import { GetCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { AppError } from '../middleware/errorHandler'
import type { Session, Exercise, Phase, SessionStatus, SessionWellness } from '@powerlifting/types'

/**
 * Resolve a version string to the actual SK.
 */
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

/**
 * Create a new session
 */
export async function createSession(
  pk: string,
  version: string,
  session: Session
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
    ProjectionExpression: 'sessions, phases',
  })

  const result = await docClient.send(getCommand)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]
  const phases = (result.Item.phases ?? []) as Phase[]

  // Check if session with this date already exists
  if (sessions.some(s => s.date === session.date)) {
    throw new AppError(`Session with date ${session.date} already exists`, 400)
  }

  // Derive week_number and phase for the new session
  const weekMatch = session.week?.match(/W(\d+)/)
  const weekNumber = weekMatch ? parseInt(weekMatch[1], 10) : 1
  const sessionBlock = session.block ?? 'current'

  // Resolve phase scoped to the session's block
  let resolvedPhase: Phase = { name: 'Unknown', intent: '', start_week: weekNumber, end_week: weekNumber, block: sessionBlock }
  if (phases && phases.length > 0) {
    const phase = phases.find(p =>
      (p.block ?? 'current') === sessionBlock &&
      weekNumber >= p.start_week &&
      weekNumber <= p.end_week
    )
    if (phase) resolvedPhase = phase
  }

  const newSession: Session = {
    ...session,
    week_number: weekNumber,
    phase: resolvedPhase,
    block: sessionBlock,
  }

  sessions.push(newSession)
  sessions.sort((a, b) => a.date.localeCompare(b.date))

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
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
 * Delete a session by index
 */
export async function deleteSession(
  pk: string,
  version: string,
  date: string,
  index: number
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  sessions.splice(index, 1)

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
    UpdateExpression: 'SET sessions = :sessions, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':sessions': sessions,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}

export async function getSession(pk: string, version: string, date: string, index: number): Promise<Session | null> {
  const sk = await resolveVersionSk(pk, version)
  const command = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
    ProjectionExpression: 'sessions',
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]
  const session = sessions[index]
  if (!session) {
    throw new AppError(`Session at index ${index} not found`, 404)
  }
  // Validate date matches for safety
  if (session.date !== date) {
    throw new AppError(`Session at index ${index} has date ${session.date}, expected ${date}`, 409)
  }
  return session
}

/**
 * Update an entire session at a specific index
 */
export async function updateSession(
  pk: string,
  version: string,
  date: string,
  index: number,
  session: Session
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  sessions[index] = session

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
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
 * Reschedule a session to a new date
 */
export async function rescheduleSession(
  pk: string,
  version: string,
  date: string,
  index: number,
  newDate: string,
  newDay: string
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  sessions[index] = {
    ...sessions[index],
    date: newDate,
    day: newDay,
  }

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
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
 * Mark a session as complete with optional RPE and body weight
 */
export async function completeSession(
  pk: string,
  version: string,
  date: string,
  index: number,
  data: { rpe?: number; bodyWeightKg?: number; notes?: string; wellness?: SessionWellness | undefined }
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  sessions[index] = {
    ...sessions[index],
    completed: true,
    session_rpe: data.rpe ?? sessions[index].session_rpe,
    body_weight_kg: data.bodyWeightKg ?? sessions[index].body_weight_kg,
    session_notes: data.notes ?? sessions[index].session_notes,
    wellness: data.wellness ?? sessions[index].wellness,
  }

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
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
 * Update only the status field on a session
 */
export async function updateSessionStatus(
  pk: string,
  version: string,
  date: string,
  index: number,
  status: SessionStatus
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  sessions[index] = {
    ...sessions[index],
    status,
    completed: status === 'completed' ? true : sessions[index].completed,
  }

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
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
 * Add an exercise to a session
 */
export async function addExercise(
  pk: string,
  version: string,
  date: string,
  index: number,
  exercise: Exercise
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  sessions[index].exercises.push(exercise)

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
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
 * Remove an exercise from a session
 */
export async function removeExercise(
  pk: string,
  version: string,
  date: string,
  index: number,
  exerciseIndex: number
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  if (exerciseIndex < 0 || exerciseIndex >= sessions[index].exercises.length) {
    throw new AppError(`Exercise index ${exerciseIndex} out of range`, 400)
  }

  sessions[index].exercises.splice(exerciseIndex, 1)

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
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
 * Update a single field on an exercise
 */
export async function updateExerciseField(
  pk: string,
  version: string,
  date: string,
  index: number,
  exerciseIndex: number,
  field: keyof Exercise,
  value: unknown
): Promise<void> {
  const sk = await resolveVersionSk(pk, version)
  const getCommand = new GetCommand({
    TableName: TABLE,
    Key: { pk, sk },
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

  if (exerciseIndex < 0 || exerciseIndex >= sessions[index].exercises.length) {
    throw new AppError(`Exercise index ${exerciseIndex} out of range`, 400)
  }

  ;(sessions[index].exercises[exerciseIndex] as any)[field] = value

  const updateCommand = new UpdateCommand({
    TableName: TABLE,
    Key: { pk, sk },
    UpdateExpression: 'SET sessions = :sessions, #meta.updated_at = :now',
    ExpressionAttributeNames: { '#meta': 'meta' },
    ExpressionAttributeValues: {
      ':sessions': sessions,
      ':now': new Date().toISOString(),
    },
  })

  await docClient.send(updateCommand)
}
