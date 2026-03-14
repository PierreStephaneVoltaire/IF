import type { Phase, Session } from '@powerlifting/types'

// Colors assigned by index in program.phases — adding/renaming phases requires no code change
const PHASE_PALETTE = [
  '#94a3b8', // index 0 - slate
  '#3b82f6', // index 1 - blue
  '#f97316', // index 2 - orange
  '#ef4444', // index 3 - red
  '#14b8a6', // index 4 - teal
  '#a855f7', // index 5 - purple
  '#22c55e', // index 6 - green
  '#eab308', // index 7 - yellow
]

/**
 * Get the color for a phase based on its position in the phases array.
 * This ensures colors are data-driven, not hardcoded by phase name.
 */
export function phaseColor(phase: Phase, allPhases: Phase[]): string {
  const index = allPhases.findIndex(p => p.name === phase.name)
  return PHASE_PALETTE[index >= 0 ? index % PHASE_PALETTE.length : 0]
}

/**
 * Build a map from week number to Phase for O(1) lookup.
 */
export function buildPhaseMap(phases: Phase[]): Map<number, Phase> {
  const map = new Map<number, Phase>()
  for (const phase of phases) {
    for (let w = phase.start_week; w <= phase.end_week; w++) {
      map.set(w, phase)
    }
  }
  return map
}

/**
 * Filter sessions by phase name.
 */
export function sessionsByPhase(sessions: Session[], phaseName: string): Session[] {
  return sessions.filter(s => s.phase.name === phaseName)
}

/**
 * Get unique phase names from sessions.
 */
export function uniquePhaseNames(sessions: Session[]): string[] {
  const names = new Set<string>()
  sessions.forEach(s => names.add(s.phase.name))
  return Array.from(names)
}
