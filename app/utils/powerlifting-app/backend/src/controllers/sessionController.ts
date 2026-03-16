import { GetCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { AppError } from '../middleware/errorHandler'
import type { Session, Exercise, Phase } from '@powerlifting/types'

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
 * Create a new session
 */
export async function createSession(
  version: string,
  session: Session
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

  // Check if session with this date already exists
  if (sessions.some(s => s.date === session.date)) {
    throw new AppError(`Session with date ${session.date} already exists`, 400)
  }

  // Derive week_number and phase for the new session
  const weekMatch = session.week?.match(/W(\d+)/)
  const weekNumber = weekMatch ? parseInt(weekMatch[1], 10) : 1

  // Resolve phase from program phases
  let resolvedPhase: Phase = { name: 'Unknown', intent: '', start_week: weekNumber, end_week: weekNumber }
  if (phases && phases.length > 0) {
    const phase = phases.find(p => weekNumber >= p.start_week && weekNumber <= p.end_week)
    if (phase) resolvedPhase = phase
  }

  const newSession: Session = {
    ...session,
    week_number: weekNumber,
    phase: resolvedPhase,
  }

  sessions.push(newSession)
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
 * Delete a session by date
 */
export async function deleteSession(
  version: string,
  date: string
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
  const sessionIndex = sessions.findIndex(s => s.date === date)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${date} not found`, 404)
  }

  sessions.splice(sessionIndex, 1)

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
 * Get a specific program and find a session by date
 */
export async function getSession(version: string, date: string): Promise<Session | null> {
  const sk = await resolveVersionSk(version)
  const command = new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    ProjectionExpression: 'sessions',
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    throw new AppError(`Program version ${version} not found`, 404)
  }

  const sessions = (result.Item.sessions ?? []) as Session[]
  return sessions.find(s => s.date === date) || null
}

/**
 * Update an entire session at a specific date
 */
export async function updateSession(
  version: string,
  date: string,
  session: Session
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
  const sessionIndex = sessions.findIndex(s => s.date === date)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${date} not found`, 404)
  }

  sessions[sessionIndex] = session

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
 * Reschedule a session to a new date
 */
export async function rescheduleSession(
  version: string,
  oldDate: string,
  newDate: string,
  newDay: string
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
  const sessionIndex = sessions.findIndex(s => s.date === oldDate)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${oldDate} not found`, 404)
  }

  sessions[sessionIndex] = {
    ...sessions[sessionIndex],
    date: newDate,
    day: newDay,
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

/**
 * Mark a session as complete with optional RPE and body weight
 */
export async function completeSession(
  version: string,
  date: string,
  data: { rpe?: number; bodyWeightKg?: number; notes?: string }
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
  const sessionIndex = sessions.findIndex(s => s.date === date)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${date} not found`, 404)
  }

  sessions[sessionIndex] = {
    ...sessions[sessionIndex],
    completed: true,
    session_rpe: data.rpe ?? sessions[sessionIndex].session_rpe,
    body_weight_kg: data.bodyWeightKg ?? sessions[sessionIndex].body_weight_kg,
    session_notes: data.notes ?? sessions[sessionIndex].session_notes,
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

/**
 * Add an exercise to a session
 */
export async function addExercise(
  version: string,
  date: string,
  exercise: Exercise
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
  const sessionIndex = sessions.findIndex(s => s.date === date)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${date} not found`, 404)
  }

  sessions[sessionIndex].exercises.push(exercise)

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
 * Remove an exercise from a session
 */
export async function removeExercise(
  version: string,
  date: string,
  exerciseIndex: number
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
  const sessionIndex = sessions.findIndex(s => s.date === date)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${date} not found`, 404)
  }

  if (exerciseIndex < 0 || exerciseIndex >= sessions[sessionIndex].exercises.length) {
    throw new AppError(`Exercise index ${exerciseIndex} out of range`, 400)
  }

  sessions[sessionIndex].exercises.splice(exerciseIndex, 1)

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
 * Update a single field on an exercise
 */
export async function updateExerciseField(
  version: string,
  date: string,
  exerciseIndex: number,
  field: keyof Exercise,
  value: unknown
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
  const sessionIndex = sessions.findIndex(s => s.date === date)

  if (sessionIndex === -1) {
    throw new AppError(`Session with date ${date} not found`, 404)
  }

  if (exerciseIndex < 0 || exerciseIndex >= sessions[sessionIndex].exercises.length) {
    throw new AppError(`Exercise index ${exerciseIndex} out of range`, 400)
  }

  ;(sessions[sessionIndex].exercises[exerciseIndex] as any)[field] = value

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
