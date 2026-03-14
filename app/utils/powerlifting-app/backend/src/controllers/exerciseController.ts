import { GetCommand, PutCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import type { GlossaryExercise, GlossaryStore } from '@powerlifting/types'
import { v4 as uuidv4 } from 'uuid'

const PK = 'operator'
const GLOSSARY_SK = 'glossary#v1'

/**
 * Get the exercise glossary
 */
export async function getGlossary(): Promise<GlossaryStore> {
  const command = new GetCommand({
    TableName: TABLE,
    Key: {
      pk: PK,
      sk: GLOSSARY_SK,
    },
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    // Return empty glossary if not found
    return {
      pk: PK,
      sk: GLOSSARY_SK,
      exercises: [],
      updated_at: new Date().toISOString(),
    }
  }

  return result.Item as GlossaryStore
}

/**
 * Add or update an exercise in the glossary
 */
export async function upsertExercise(exercise: GlossaryExercise): Promise<void> {
  const glossary = await getGlossary()

  // Generate ID if not provided
  if (!exercise.id) {
    exercise.id = uuidv4()
  }

  // Find existing exercise by ID
  const existingIndex = glossary.exercises.findIndex(e => e.id === exercise.id)

  if (existingIndex >= 0) {
    // Update existing
    glossary.exercises[existingIndex] = exercise
  } else {
    // Add new
    glossary.exercises.push(exercise)
  }

  // Sort by name
  glossary.exercises.sort((a, b) => a.name.localeCompare(b.name))
  glossary.updated_at = new Date().toISOString()

  const command = new PutCommand({
    TableName: TABLE,
    Item: glossary,
  })

  await docClient.send(command)
}

/**
 * Remove an exercise from the glossary
 */
export async function removeExercise(exerciseId: string): Promise<void> {
  const glossary = await getGlossary()

  glossary.exercises = glossary.exercises.filter(e => e.id !== exerciseId)
  glossary.updated_at = new Date().toISOString()

  const command = new PutCommand({
    TableName: TABLE,
    Item: glossary,
  })

  await docClient.send(command)
}

/**
 * Get exercise by ID
 */
export async function getExerciseById(exerciseId: string): Promise<GlossaryExercise | null> {
  const glossary = await getGlossary()
  return glossary.exercises.find(e => e.id === exerciseId) || null
}

/**
 * Search exercises by name
 */
export async function searchExercises(query: string): Promise<GlossaryExercise[]> {
  const glossary = await getGlossary()
  const lowerQuery = query.toLowerCase()

  return glossary.exercises.filter(e =>
    e.name.toLowerCase().includes(lowerQuery) ||
    e.primary_muscles.some(m => m.toLowerCase().includes(lowerQuery))
  )
}
