import { GetCommand, PutCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { invokeToolDirect } from '../utils/agent'
import type { GlossaryExercise, GlossaryStore } from '@powerlifting/types'
import { v4 as uuidv4 } from 'uuid'

const GLOSSARY_SK = 'glossary#v1'
const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'http://localhost:3002'

/**
 * Get the exercise glossary
 */
export async function getGlossary(pk: string): Promise<GlossaryStore> {
  const command = new GetCommand({
    TableName: TABLE,
    Key: {
      pk,
      sk: GLOSSARY_SK,
    },
  })

  const result = await docClient.send(command)

  if (!result.Item) {
    // Return empty glossary if not found
    return {
      pk,
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
export async function upsertExercise(pk: string, exercise: GlossaryExercise): Promise<void> {
  const glossary = await getGlossary(pk)

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

  // Fire-and-forget AI fatigue profile estimation if profile is missing and not manually set
  if (!exercise.fatigue_profile && exercise.fatigue_profile_source !== 'manual') {
    fetch(`${INTERNAL_API_URL}/api/analytics/fatigue-profile/estimate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: exercise.name,
        category: exercise.category,
        equipment: exercise.equipment,
        primary_muscles: exercise.primary_muscles,
        secondary_muscles: exercise.secondary_muscles,
        cues: exercise.cues,
        notes: exercise.notes,
      }),
    })
      .then(res => res.json())
      .then(({ data: profile }) => {
        if (!profile) return
        return updateExerciseProfile(pk, exercise.id, {
          fatigue_profile: { axial: profile.axial, neural: profile.neural, peripheral: profile.peripheral, systemic: profile.systemic },
          fatigue_profile_source: 'ai_estimated',
          fatigue_profile_reasoning: profile.reasoning,
        })
      })
      .catch(err => console.error('Fatigue profile estimation failed:', err))
  }
}

/**
 * Update only the fatigue profile fields of an exercise in the glossary
 */
async function updateExerciseProfile(
  pk: string,
  exerciseId: string,
  profile: { fatigue_profile: GlossaryExercise['fatigue_profile']; fatigue_profile_source: GlossaryExercise['fatigue_profile_source']; fatigue_profile_reasoning: string | null }
): Promise<void> {
  const glossary = await getGlossary(pk)
  const idx = glossary.exercises.findIndex(e => e.id === exerciseId)
  if (idx < 0) return

  glossary.exercises[idx] = {
    ...glossary.exercises[idx],
    ...profile,
  }
  glossary.updated_at = new Date().toISOString()

  const command = new PutCommand({ TableName: TABLE, Item: glossary })
  await docClient.send(command)
}

export async function removeExercise(pk: string, exerciseId: string): Promise<void> {
  const glossary = await getGlossary(pk)

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
export async function getExerciseById(pk: string, exerciseId: string): Promise<GlossaryExercise | null> {
  const glossary = await getGlossary(pk)
  return glossary.exercises.find(e => e.id === exerciseId) || null
}

/**
 * Search exercises by name
 */
export async function searchExercises(pk: string, query: string): Promise<GlossaryExercise[]> {
  const glossary = await getGlossary(pk)
  const lowerQuery = query.toLowerCase()

  return glossary.exercises.filter(e =>
    e.name.toLowerCase().includes(lowerQuery) ||
    e.primary_muscles.some(m => m.toLowerCase().includes(lowerQuery))
  )
}

/**
 * Archive an exercise
 */
export async function archiveExercise(pk: string, id: string): Promise<void> {
  const glossary = await getGlossary(pk)
  const idx = glossary.exercises.findIndex(e => e.id === id)
  if (idx < 0) return

  glossary.exercises[idx].archived = true
  glossary.updated_at = new Date().toISOString()

  await docClient.send(new PutCommand({ TableName: TABLE, Item: glossary }))
}

/**
 * Unarchive an exercise
 */
export async function unarchiveExercise(pk: string, id: string): Promise<void> {
  const glossary = await getGlossary(pk)
  const idx = glossary.exercises.findIndex(e => e.id === id)
  if (idx < 0) return

  glossary.exercises[idx].archived = false
  glossary.updated_at = new Date().toISOString()

  await docClient.send(new PutCommand({ TableName: TABLE, Item: glossary }))
}

/**
 * Set e1RM estimate for an exercise
 */
export async function setE1rmEstimate(
  pk: string,
  id: string,
  valueKg: number,
  method: 'manual' | 'ai_backfill' | 'logged' = 'manual'
): Promise<void> {
  const glossary = await getGlossary(pk)
  const idx = glossary.exercises.findIndex(e => e.id === id)
  if (idx < 0) return

  glossary.exercises[idx].e1rm_estimate = {
    value_kg: valueKg,
    method,
    basis: method === 'manual' ? 'Manual entry' : '',
    confidence: method === 'manual' ? 'medium' : 'low',
    set_at: new Date().toISOString(),
    manually_overridden: method === 'manual'
  }
  glossary.updated_at = new Date().toISOString()

  await docClient.send(new PutCommand({ TableName: TABLE, Item: glossary }))
}

/**
 * AI estimate e1RM for an exercise
 */
export async function estimateExerciseE1rm(id: string): Promise<any> {
  return invokeToolDirect('glossary_estimate_e1rm', { id })
}

/**
 * AI estimate fatigue profile for an exercise
 */
export async function estimateExerciseFatigue(id: string): Promise<any> {
  return invokeToolDirect('glossary_estimate_fatigue', { id })
}
