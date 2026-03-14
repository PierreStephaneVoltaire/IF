import type { Program, Session, Phase } from '@powerlifting/types'

/**
 * Parse week number from a week label string.
 * Examples: 'W7 (Intensification)' -> 7, 'W1 (Warmup)' -> 1, 'W10' -> 10
 */
function parseWeekNumber(weekLabel: string): number {
  const match = weekLabel.match(/W(\d+)/)
  return match ? parseInt(match[1], 10) : 0
}

/**
 * Resolve the correct Phase object for a given week label using program.phases.
 * No hardcoded phase names anywhere — purely data-driven from the JSON.
 */
function resolvePhase(weekLabel: string, phases: Phase[]): Phase {
  const weekNum = parseWeekNumber(weekLabel)
  const phase = phases.find(p => weekNum >= p.start_week && weekNum <= p.end_week)
  return phase ?? { name: 'Unknown', intent: '', start_week: weekNum, end_week: weekNum }
}

/**
 * Transform DynamoDB item into a clean Program object.
 * Note: DynamoDBDocumentClient already unmarshalls data automatically,
 * so we receive plain JavaScript objects, not raw DynamoDB JSON.
 * Derives week_number and resolves phase for each session.
 */
export function transformProgram(item: Record<string, unknown>): Program {
  const program = item as unknown as Program

  // Derive week_number and resolve phase for each session
  program.sessions = program.sessions.map(session => ({
    ...session,
    week_number: parseWeekNumber(session.week),
    phase: resolvePhase(session.week, program.phases),
  }))

  // Sort sessions by date
  program.sessions.sort((a, b) => a.date.localeCompare(b.date))

  return program
}

/**
 * Get the current week number based on program start date.
 */
export function getCurrentWeek(programStart: string): number {
  const start = new Date(programStart)
  const now = new Date()
  const diffTime = now.getTime() - start.getTime()
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))
  return Math.max(1, Math.floor(diffDays / 7) + 1)
}
