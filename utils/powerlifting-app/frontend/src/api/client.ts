import axios from 'axios'
import type {
  Program,
  ProgramListItem,
  Session,
  PlannedExercise,
  Exercise,
  MaxEntry,
  WeightEntry,
  GlossaryExercise,
  ApiResponse,
  Phase,
  SupplementPhase,
  DietNote,
  Competition,
  SessionVideo,
  LiftResults,
  VideoLibraryItem,
  VideoLibraryResponse,
  FatigueProfile,
  LiftProfile,
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
  date: string,
  index: number
): Promise<void> {
  await api.delete(`/sessions/${version}/${date}/${index}`)
}

export async function fetchSession(
  version: string,
  date: string,
  index: number
): Promise<Session | null> {
  const res = await api.get<ApiResponse<Session | null>>(
    `/sessions/${version}/${date}/${index}`
  )
  return res.data.data
}

export async function updateSession(
  version: string,
  date: string,
  index: number,
  session: Session
): Promise<void> {
  await api.put(`/sessions/${version}/${date}/${index}`, session)
}

export async function updatePlannedExercises(
  version: string,
  date: string,
  index: number,
  plannedExercises: PlannedExercise[]
): Promise<void> {
  await api.put(`/programs/${version}/designer/${date}/${index}/planned-exercises`, { planned_exercises: plannedExercises })
}

export async function rescheduleSession(
  version: string,
  date: string,
  index: number,
  newDate: string,
  newDay: string
): Promise<void> {
  await api.patch(`/sessions/${version}/${date}/${index}/reschedule`, {
    newDate,
    newDay,
  })
}

export async function completeSession(
  version: string,
  date: string,
  index: number,
  data: { rpe?: number; bodyWeightKg?: number; notes?: string }
): Promise<void> {
  await api.patch(`/sessions/${version}/${date}/${index}/complete`, data)
}

export async function addExercise(
  version: string,
  date: string,
  index: number,
  exercise: Exercise
): Promise<void> {
  await api.post(`/sessions/${version}/${date}/${index}/exercise`, exercise)
}

export async function updateExerciseField(
  version: string,
  date: string,
  index: number,
  exerciseIndex: number,
  field: keyof Exercise,
  value: unknown
): Promise<void> {
  await api.patch(
    `/sessions/${version}/${date}/${index}/exercise/${exerciseIndex}`,
    { field, value }
  )
}

export async function removeExercise(
  version: string,
  date: string,
  index: number,
  exerciseIndex: number
): Promise<void> {
  await api.delete(`/sessions/${version}/${date}/${index}/exercise/${exerciseIndex}`)
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

// ─── Supplements ──────────────────────────────────────────────────────────────

export async function fetchSupplementPhases(
  version: string
): Promise<SupplementPhase[]> {
  const res = await api.get<ApiResponse<SupplementPhase[]>>(`/supplements/${version}`)
  return res.data.data
}

export async function updateSupplementPhases(
  version: string,
  phases: SupplementPhase[]
): Promise<void> {
  await api.put(`/supplements/${version}`, { phases })
}

// ─── Diet Notes ───────────────────────────────────────────────────────────────

export async function fetchDietNotes(version: string): Promise<DietNote[]> {
  const res = await api.get<ApiResponse<DietNote[]>>(`/diet-notes/${version}`)
  return res.data.data
}

export async function updateDietNotes(
  version: string,
  dietNotes: DietNote[]
): Promise<void> {
  await api.put(`/diet-notes/${version}`, { dietNotes })
}

// ─── Competitions ─────────────────────────────────────────────────────────────

export async function fetchCompetitions(version: string): Promise<Competition[]> {
  const res = await api.get<ApiResponse<Competition[]>>(`/competitions/${version}`)
  return res.data.data
}

export async function updateCompetitions(
  version: string,
  competitions: Competition[]
): Promise<void> {
  await api.put(`/competitions/${version}`, { competitions })
}

export async function migrateLastComp(version: string): Promise<Competition[]> {
  const res = await api.post<ApiResponse<Competition[]>>(`/competitions/${version}/migrate`)
  return res.data.data
}

export async function completeCompetition(
  version: string,
  date: string,
  results: LiftResults,
  bodyWeightKg: number
): Promise<void> {
  await api.patch(`/competitions/${version}/${date}/complete`, { results, bodyWeightKg })
}

// ─── Videos ───────────────────────────────────────────────────────────────────

export async function getVideos(
  version: string = 'current',
  exercise?: string,
  sort: 'newest' | 'oldest' = 'newest'
): Promise<{ videos: VideoLibraryItem[]; exercises: string[] }> {
  const params = new URLSearchParams()
  if (exercise) params.set('exercise', exercise)
  params.set('sort', sort)
  const res = await api.get<ApiResponse<{ videos: VideoLibraryItem[]; exercises: string[] }>>(
    `/videos?version=${version}&${params}`
  )
  return res.data.data
}

export async function removeSessionVideo(
  version: string,
  sessionDate: string,
  videoId: string
): Promise<void> {
  await api.delete(`/videos/${version}/${sessionDate}/${videoId}`)
}

// ─── Lift Profiles ────────────────────────────────────────────────────────────

export async function updateLiftProfiles(
  version: string,
  liftProfiles: LiftProfile[]
): Promise<void> {
  await api.put(`/programs/${version}/lift-profiles`, { liftProfiles })
}

// ─── Fatigue Profile ──────────────────────────────────────────────────────────

export async function estimateFatigueProfile(exercise: {
  name: string
  category?: string
  equipment?: string
  primary_muscles?: string[]
  secondary_muscles?: string[]
  cues?: string[]
  notes?: string
}): Promise<FatigueProfile & { reasoning: string }> {
  const res = await api.post<ApiResponse<FatigueProfile & { reasoning: string }>>(
    '/analytics/fatigue-profile/estimate',
    exercise
  )
  return res.data.data
}

export default api
