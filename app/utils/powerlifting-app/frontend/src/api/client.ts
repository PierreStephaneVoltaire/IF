import axios from 'axios'
import type {
  Program,
  ProgramListItem,
  Session,
  Exercise,
  MaxEntry,
  WeightEntry,
  GlossaryExercise,
  ApiResponse,
  Phase,
} from '@powerlifting/types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// ─── Programs ────────────────────────────────────────────────────────────────

export async function fetchPrograms(): Promise<ProgramListItem[]> {
  const res = await api.get<ApiResponse<ProgramListItem[]>>('/programs')
  return res.data.data
}

export async function fetchProgram(version: string): Promise<Program> {
  const res = await api.get<ApiResponse<Program>>(`/programs/${version}`)
  return res.data.data
}

export async function updateMetaField(
  version: string,
  field: string,
  value: unknown
): Promise<void> {
  await api.put(`/programs/${version}/meta`, { field, value })
}

export async function forkProgram(
  version: string,
  label?: string
): Promise<string> {
  const res = await api.post<ApiResponse<{ version: string }>>(
    `/programs/${version}/fork`,
    { label }
  )
  return res.data.data.version
}

// ─── Sessions ────────────────────────────────────────────────────────────────

export async function createSession(
  version: string,
  session: Partial<Session> & { date: string }
): Promise<Session> {
  const res = await api.post<ApiResponse<{ success: boolean; session: Session }>>(
    `/sessions/${version}`,
    session
  )
  return res.data.data.session
}

export async function deleteSession(
  version: string,
  date: string
): Promise<void> {
  await api.delete(`/sessions/${version}/${date}`)
}

export async function fetchSession(
  version: string,
  date: string
): Promise<Session | null> {
  const res = await api.get<ApiResponse<Session | null>>(
    `/sessions/${version}/${date}`
  )
  return res.data.data
}

export async function updateSession(
  version: string,
  date: string,
  session: Session
): Promise<void> {
  await api.put(`/sessions/${version}/${date}`, session)
}

export async function rescheduleSession(
  version: string,
  oldDate: string,
  newDate: string,
  newDay: string
): Promise<void> {
  await api.patch(`/sessions/${version}/${oldDate}/reschedule`, {
    newDate,
    newDay,
  })
}

export async function completeSession(
  version: string,
  date: string,
  data: { rpe?: number; bodyWeightKg?: number; notes?: string }
): Promise<void> {
  await api.patch(`/sessions/${version}/${date}/complete`, data)
}

export async function addExercise(
  version: string,
  date: string,
  exercise: Exercise
): Promise<void> {
  await api.post(`/sessions/${version}/${date}/exercise`, exercise)
}

export async function updateExerciseField(
  version: string,
  date: string,
  exerciseIndex: number,
  field: keyof Exercise,
  value: unknown
): Promise<void> {
  await api.patch(
    `/sessions/${version}/${date}/exercise/${exerciseIndex}`,
    { field, value }
  )
}

export async function removeExercise(
  version: string,
  date: string,
  exerciseIndex: number
): Promise<void> {
  await api.delete(`/sessions/${version}/${date}/exercise/${exerciseIndex}`)
}

// ─── Maxes ───────────────────────────────────────────────────────────────────

export async function fetchMaxes(version: string): Promise<{
  targets: { squat_kg: number; bench_kg: number; deadlift_kg: number; total_kg: number }
  history: MaxEntry[]
}> {
  const res = await api.get<
    ApiResponse<{
      targets: { squat_kg: number; bench_kg: number; deadlift_kg: number; total_kg: number }
      history: MaxEntry[]
    }>
  >(`/maxes/${version}`)
  return res.data.data
}

export async function updateTargetMaxes(
  version: string,
  maxes: { squat_kg: number; bench_kg: number; deadlift_kg: number }
): Promise<void> {
  await api.put(`/maxes/${version}`, maxes)
}

export async function updateBodyWeight(
  version: string,
  weightKg: number
): Promise<void> {
  await api.put(`/programs/${version}/body-weight`, { weightKg })
}

export async function updatePhases(
  version: string,
  phases: Phase[]
): Promise<void> {
  await api.put(`/programs/${version}/phases`, { phases })
}

export async function addMaxEntry(
  version: string,
  entry: MaxEntry
): Promise<void> {
  await api.post(`/maxes/${version}/history`, entry)
}

// ─── Weight Log ──────────────────────────────────────────────────────────────

export async function fetchWeightLog(
  version: string
): Promise<WeightEntry[]> {
  const res = await api.get<ApiResponse<{ entries: WeightEntry[] }>>(
    `/weight/${version}`
  )
  return res.data.data.entries
}

export async function addWeightEntry(
  version: string,
  entry: WeightEntry
): Promise<void> {
  await api.post(`/weight/${version}`, entry)
}

export async function removeWeightEntry(
  version: string,
  date: string
): Promise<void> {
  await api.delete(`/weight/${version}/${date}`)
}

// ─── Exercises (Glossary) ────────────────────────────────────────────────────

export async function fetchGlossary(): Promise<GlossaryExercise[]> {
  const res = await api.get<ApiResponse<GlossaryExercise[]>>('/exercises')
  return res.data.data
}

export async function searchExercises(query: string): Promise<GlossaryExercise[]> {
  const res = await api.get<ApiResponse<GlossaryExercise[]>>(
    `/exercises/search?q=${encodeURIComponent(query)}`
  )
  return res.data.data
}

export async function upsertExercise(
  exercise: GlossaryExercise
): Promise<void> {
  if (exercise.id) {
    await api.put(`/exercises/${exercise.id}`, exercise)
  } else {
    await api.post('/exercises', exercise)
  }
}

export async function deleteExercise(exerciseId: string): Promise<void> {
  await api.delete(`/exercises/${exerciseId}`)
}

export default api
