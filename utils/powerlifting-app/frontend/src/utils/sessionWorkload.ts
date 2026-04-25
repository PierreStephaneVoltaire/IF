import type { GlossaryExercise, MuscleGroup, Session } from '@powerlifting/types'
import { normalizeExerciseName } from './volume'

type WorkoutEntry = Pick<Session['exercises'][number], 'name' | 'sets' | 'reps' | 'kg'>

interface MuscleContribution {
  primary: MuscleGroup[]
  secondary: MuscleGroup[]
  tertiary: MuscleGroup[]
}

function buildGlossaryLookup(glossary: GlossaryExercise[]): Map<string, MuscleContribution> {
  const lookup = new Map<string, MuscleContribution>()
  for (const ex of glossary) {
    lookup.set(normalizeExerciseName(ex.name), {
      primary: ex.primary_muscles,
      secondary: ex.secondary_muscles,
      tertiary: ex.tertiary_muscles ?? [],
    })
  }
  return lookup
}

export function sessionMuscleSets(
  entries: WorkoutEntry[],
  glossary: GlossaryExercise[]
): Partial<Record<MuscleGroup, number>> {
  const lookup = buildGlossaryLookup(glossary)
  const volumes: Partial<Record<MuscleGroup, number>> = {}

  for (const ex of entries) {
    const muscles = lookup.get(normalizeExerciseName(ex.name))
    if (!muscles) continue

    const sets = ex.sets || 0
    if (sets <= 0) continue

    for (const muscle of muscles.primary) {
      volumes[muscle] = (volumes[muscle] ?? 0) + sets
    }
    for (const muscle of muscles.secondary) {
      volumes[muscle] = (volumes[muscle] ?? 0) + sets * 0.5
    }
    for (const muscle of muscles.tertiary) {
      volumes[muscle] = (volumes[muscle] ?? 0) + sets * 0.25
    }
  }

  return volumes
}

export function sessionEntriesFromSession(session: Session): WorkoutEntry[] {
  return session.exercises.length > 0 ? session.exercises : session.planned_exercises ?? []
}
