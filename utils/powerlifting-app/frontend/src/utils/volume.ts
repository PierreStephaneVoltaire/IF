import type { Session, Exercise, GlossaryExercise, MuscleGroup } from '@powerlifting/types'

export type LiftCategory = 'squat' | 'bench' | 'deadlift' | 'upper_accessory' | 'lower_accessory' | 'core_accessory'

const ALL_CATEGORIES: LiftCategory[] = ['squat', 'bench', 'deadlift', 'upper_accessory', 'lower_accessory', 'core_accessory']

function zeroCategoryRecord(): Record<LiftCategory, number> {
  return { squat: 0, bench: 0, deadlift: 0, upper_accessory: 0, lower_accessory: 0, core_accessory: 0 }
}

/**
 * Calculate volume (sets * reps * kg) for a single exercise.
 */
export function exerciseVolume(ex: Exercise): number {
  if (!ex.kg || !ex.sets || !ex.reps) return 0
  return ex.sets * ex.reps * ex.kg
}

/**
 * Calculate total volume for a session.
 */
export function sessionVolume(session: Session): number {
  return session.exercises.reduce((sum, ex) => sum + exerciseVolume(ex), 0)
}

/**
 * Map exercise names to lift categories (6-category system).
 */
const LIFT_CATEGORY_MAP: Record<string, LiftCategory> = {
  // ─── Squat ──────────────────────────────────────────────────────
  'Squat': 'squat',
  'Squat (Backout Heavy)': 'squat',
  'Squat (Backout Light)': 'squat',
  'Back Squat': 'squat',
  'Front Squat': 'squat',
  'Box Squat': 'squat',
  'Pause Squat': 'squat',
  'Tempo Squat': 'squat',
  'Safety Bar Squat': 'squat',
  'Hack Squat': 'squat',

  // ─── Bench ──────────────────────────────────────────────────────
  'Bench Press': 'bench',
  'Bench Press (Backout)': 'bench',
  'Pause Bench Press': 'bench',
  'Spoto Press': 'bench',
  'Close-Grip Bench Press': 'bench',
  'Wide-Grip Bench Press': 'bench',
  'Floor Press': 'bench',
  'Incline Bench Press': 'bench',

  // ─── Deadlift ───────────────────────────────────────────────────
  'Deadlift': 'deadlift',
  'Deadlift (Backout)': 'deadlift',
  'Conventional Deadlift': 'deadlift',
  'Sumo Deadlift': 'deadlift',
  'Stiff-Leg Deadlift': 'deadlift',
  'Deficit Deadlift': 'deadlift',
  'Rack Pull': 'deadlift',
  'Block Pull': 'deadlift',

  // ─── Upper accessory ────────────────────────────────────────────
  'Romanian Deadlift': 'upper_accessory',
  'RDL': 'upper_accessory',
  'OHP': 'upper_accessory',
  'Overhead Press': 'upper_accessory',
  'Shoulder Press': 'upper_accessory',
  'DB Shoulder Press': 'upper_accessory',
  'Push Press': 'upper_accessory',
  'Lat Pulldown': 'upper_accessory',
  'Row': 'upper_accessory',
  'Barbell Row': 'upper_accessory',
  'DB Row': 'upper_accessory',
  'Cable Row': 'upper_accessory',
  'Face Pull': 'upper_accessory',
  'Pull-up': 'upper_accessory',
  'Weighted Pull-up': 'upper_accessory',
  'Chin-up': 'upper_accessory',
  'Dip': 'upper_accessory',
  'Curl': 'upper_accessory',
  'Barbell Curl': 'upper_accessory',
  'DB Curl': 'upper_accessory',
  'Hammer Curl': 'upper_accessory',
  'Tricep Pushdown': 'upper_accessory',
  'Skull Crusher': 'upper_accessory',
  'Lateral Raise': 'upper_accessory',
  'Rear Delt Fly': 'upper_accessory',
  'Shrug': 'upper_accessory',
  'DB Bench Press': 'upper_accessory',
  'DB Incline Press': 'upper_accessory',
  'Push-up': 'upper_accessory',
  'Cable Curl': 'upper_accessory',
  'Preacher Curl': 'upper_accessory',
  'Incline DB Curl': 'upper_accessory',
  'Tricep Extension': 'upper_accessory',
  'Overhead Tricep Extension': 'upper_accessory',

  // ─── Lower accessory ────────────────────────────────────────────
  'Leg Press': 'lower_accessory',
  'Lunges': 'lower_accessory',
  'Split Squat': 'lower_accessory',
  'Bulgarian Split Squat': 'lower_accessory',
  'Leg Curl': 'lower_accessory',
  'Nordic Hamstring Curl': 'lower_accessory',
  'Glute Ham Raise': 'lower_accessory',
  'Hip Thrust': 'lower_accessory',
  'Back Extension': 'lower_accessory',
  'Reverse Hyper': 'lower_accessory',
  'Good Morning': 'lower_accessory',
  'Leg Extension': 'lower_accessory',
  'Calf Raise': 'lower_accessory',
  'Seated Calf Raise': 'lower_accessory',

  // ─── Core accessory ─────────────────────────────────────────────
  'Plank': 'core_accessory',
  'Ab Rollout': 'core_accessory',
  'Ab Wheel': 'core_accessory',
  'Russian Twist': 'core_accessory',
  'Hanging Leg Raise': 'core_accessory',
  'Cable Crunch': 'core_accessory',
  'Pallof Press': 'core_accessory',
  'Dead Bug': 'core_accessory',
  'Side Plank': 'core_accessory',
  'Cable Woodchop': 'core_accessory',
}

/**
 * Normalize an exercise name for matching: strip parenthetical suffixes
 * like (heavy), (light), (backout), trim whitespace, lowercase.
 */
export function normalizeExerciseName(name: string): string {
  return name.replace(/\s*\(.*?\)\s*/g, ' ').trim().toLowerCase()
}

/**
 * Categorize an exercise by name. Defaults to upper_accessory.
 * Strips parenthetical suffixes and normalizes case/whitespace before lookup.
 */
export function categorizeExercise(name: string): LiftCategory {
  return LIFT_CATEGORY_MAP[name] ?? LIFT_CATEGORY_MAP[normalizeExerciseName(name)] ?? 'upper_accessory'
}

/**
 * Calculate volume by 6-category system for a list of sessions.
 */
export function volumeByCategory6(sessions: Session[]): Record<LiftCategory, number> {
  const result = zeroCategoryRecord()

  for (const session of sessions) {
    for (const ex of session.exercises) {
      const vol = exerciseVolume(ex)
      result[categorizeExercise(ex.name)] += vol
    }
  }

  return result
}

/**
 * Calculate volume by legacy 4-category system (backward compat).
 */
export function volumeByCategory(sessions: Session[]): Record<string, number> {
  const result = { squat: 0, bench: 0, deadlift: 0, accessory: 0 }

  for (const session of sessions) {
    for (const ex of session.exercises) {
      const vol = exerciseVolume(ex)
      const cat = categorizeExercise(ex.name)
      if (cat === 'squat' || cat === 'bench' || cat === 'deadlift') {
        result[cat] += vol
      } else {
        result.accessory += vol
      }
    }
  }

  return result
}

/**
 * Get weekly volume data for charting (6-category system).
 */
export function weeklyVolumeByCategory6(
  sessions: Session[]
): Array<{ week: number; squat: number; bench: number; deadlift: number; upper_accessory: number; lower_accessory: number; core_accessory: number }> {
  const weekMap = new Map<number, Record<LiftCategory, number>>()

  for (const session of sessions) {
    const week = session.week_number
    if (!weekMap.has(week)) {
      weekMap.set(week, zeroCategoryRecord())
    }
    const weekData = weekMap.get(week)!

    for (const ex of session.exercises) {
      const vol = exerciseVolume(ex)
      weekData[categorizeExercise(ex.name)] += vol
    }
  }

  return Array.from(weekMap.entries())
    .map(([week, data]) => ({ week, ...data }))
    .sort((a, b) => a.week - b.week)
}

/**
 * Get weekly volume data for charting (legacy 4-category, backward compat).
 */
export function weeklyVolumeByCategory(
  sessions: Session[]
): Array<{ week: number; squat: number; bench: number; deadlift: number; accessory: number }> {
  const weekMap = new Map<number, { squat: number; bench: number; deadlift: number; accessory: number }>()

  for (const session of sessions) {
    const week = session.week_number
    if (!weekMap.has(week)) {
      weekMap.set(week, { squat: 0, bench: 0, deadlift: 0, accessory: 0 })
    }
    const weekData = weekMap.get(week)!

    for (const ex of session.exercises) {
      const vol = exerciseVolume(ex)
      const cat = categorizeExercise(ex.name)
      if (cat === 'squat' || cat === 'bench' || cat === 'deadlift') {
        weekData[cat] += vol
      } else {
        weekData.accessory += vol
      }
    }
  }

  return Array.from(weekMap.entries())
    .map(([week, data]) => ({ week, ...data }))
    .sort((a, b) => a.week - b.week)
}

// ─── Muscle Group Utilities ──────────────────────────────────────────────────

/**
 * Build a lookup from exercise name to its muscle contributions.
 * Keys are normalized (lowered, parenthetical suffixes stripped, trimmed)
 * so that session exercise names with extra annotations still match.
 */
function buildGlossaryLookup(
  glossary: GlossaryExercise[]
): Map<string, { primary: MuscleGroup[]; secondary: MuscleGroup[] }> {
  const lookup = new Map<string, { primary: MuscleGroup[]; secondary: MuscleGroup[] }>()
  for (const ex of glossary) {
    const key = normalizeExerciseName(ex.name)
    lookup.set(key, {
      primary: ex.primary_muscles,
      secondary: ex.secondary_muscles,
    })
  }
  return lookup
}

/**
 * Calculate total volume (sets * reps * kg) per muscle group.
 * Primary muscles get full weight, secondary muscles get half weight.
 * Exercises not found in the glossary are skipped.
 */
export function volumeByMuscleGroup(
  sessions: Session[],
  glossary: GlossaryExercise[]
): Record<string, number> {
  const lookup = buildGlossaryLookup(glossary)
  const volumes: Record<string, number> = {}

  for (const session of sessions) {
    for (const ex of session.exercises) {
      const muscles = lookup.get(normalizeExerciseName(ex.name))
      if (!muscles || ex.kg === null) continue

      const vol = (ex.sets || 0) * (ex.reps || 0) * ex.kg

      for (const m of muscles.primary) {
        volumes[m] = (volumes[m] ?? 0) + vol
      }
      for (const m of muscles.secondary) {
        volumes[m] = (volumes[m] ?? 0) + vol * 0.5
      }
    }
  }

  return volumes
}

/**
 * Calculate weekly sets per muscle group.
 * Primary muscles get full set credit, secondary muscles get half set credit.
 * Exercises not found in the glossary are skipped.
 */
export function weeklySetsByMuscleGroup(
  sessions: Session[],
  glossary: GlossaryExercise[]
): Array<Record<string, number>> {
  const lookup = buildGlossaryLookup(glossary)
  const weekMap = new Map<number, Record<string, number>>()

  // Collect all muscle group names from the glossary
  const allMuscles = new Set<string>()
  for (const ex of glossary) {
    for (const m of ex.primary_muscles) allMuscles.add(m)
    for (const m of ex.secondary_muscles) allMuscles.add(m)
  }

  for (const session of sessions) {
    const week = session.week_number
    if (!weekMap.has(week)) {
      weekMap.set(week, { week })
    }
    const weekData = weekMap.get(week)!

    for (const ex of session.exercises) {
      const muscles = lookup.get(normalizeExerciseName(ex.name))
      if (!muscles) continue

      const sets = ex.sets || 0

      for (const m of muscles.primary) {
        weekData[m] = (weekData[m] ?? 0) + sets
      }
      for (const m of muscles.secondary) {
        weekData[m] = (weekData[m] ?? 0) + sets * 0.5
      }
    }
  }

  return Array.from(weekMap.values())
    .sort((a, b) => (a.week as number) - (b.week as number))
}
