import type { Session, Exercise } from '@powerlifting/types'

type LiftCategory = 'squat' | 'bench' | 'deadlift' | 'accessory'

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
 * Map exercise names to lift categories.
 */
const LIFT_CATEGORY_MAP: Record<string, LiftCategory> = {
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
  'Bench Press': 'bench',
  'Bench Press (Backout)': 'bench',
  'Pause Bench Press': 'bench',
  'Spoto Press': 'bench',
  'Close-Grip Bench Press': 'bench',
  'Wide-Grip Bench Press': 'bench',
  'Floor Press': 'bench',
  'Incline Bench Press': 'bench',
  'Deadlift': 'deadlift',
  'Deadlift (Backout)': 'deadlift',
  'Conventional Deadlift': 'deadlift',
  'Sumo Deadlift': 'deadlift',
  'Romanian Deadlift': 'deadlift',
  'RDL': 'deadlift',
  'Stiff-Leg Deadlift': 'deadlift',
  'Deficit Deadlift': 'deadlift',
  'Rack Pull': 'deadlift',
  'Block Pull': 'deadlift',
}

/**
 * Categorize an exercise by name.
 */
export function categorizeExercise(name: string): LiftCategory {
  return LIFT_CATEGORY_MAP[name] ?? 'accessory'
}

/**
 * Calculate volume by category for a list of sessions.
 */
export function volumeByCategory(sessions: Session[]): Record<LiftCategory, number> {
  const result: Record<LiftCategory, number> = {
    squat: 0,
    bench: 0,
    deadlift: 0,
    accessory: 0,
  }

  for (const session of sessions) {
    for (const ex of session.exercises) {
      const vol = exerciseVolume(ex)
      result[categorizeExercise(ex.name)] += vol
    }
  }

  return result
}

/**
 * Get weekly volume data for charting.
 */
export function weeklyVolumeByCategory(
  sessions: Session[]
): Array<{ week: number; squat: number; bench: number; deadlift: number; accessory: number }> {
  const weekMap = new Map<number, Record<LiftCategory, number>>()

  for (const session of sessions) {
    const week = session.week_number
    if (!weekMap.has(week)) {
      weekMap.set(week, { squat: 0, bench: 0, deadlift: 0, accessory: 0 })
    }
    const weekData = weekMap.get(week)!

    for (const ex of session.exercises) {
      const vol = exerciseVolume(ex)
      weekData[categorizeExercise(ex.name)] += vol
    }
  }

  const result = Array.from(weekMap.entries())
    .map(([week, data]) => ({ week, ...data }))
    .sort((a, b) => a.week - b.week)

  return result
}
