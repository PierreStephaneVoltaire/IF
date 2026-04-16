import type { Program, Session, Phase, Template, ImportPending } from '@powerlifting/types'

/**
 * Parse week number from a week label string.
 * Examples: 'W7 (Intensification)' -> 7, 'W1 (Warmup)' -> 1, 'W10' -> 10, '1' -> 1
 */
function parseWeekNumber(weekLabel: string | number | undefined): number {
  if (typeof weekLabel === 'number') {
    return weekLabel
  }
  if (!weekLabel) {
    return 0
  }
  // Try to match "W<number>" pattern first
  const match = weekLabel.match(/W(\d+)/i)
  if (match) {
    return parseInt(match[1], 10)
  }
  // Try to parse as plain number
  const num = parseInt(weekLabel, 10)
  return isNaN(num) ? 0 : num
}

/**
 * Resolve the correct Phase object for a given week number using program.phases.
 * No hardcoded phase names anywhere — purely data-driven from the JSON.
 */
function resolvePhase(weekNum: number, phases: Phase[]): Phase {
  if (weekNum <= 0 || phases.length === 0) {
    return { name: 'Unscheduled', intent: '', start_week: 0, end_week: 0 }
  }
  const phase = phases.find(p => weekNum >= p.start_week && weekNum <= p.end_week)
  return phase ?? { name: 'Unscheduled', intent: '', start_week: weekNum, end_week: weekNum }
}

/**
 * Transform DynamoDB item into a clean Program object.
 */
export function transformProgram(item: Record<string, unknown>): Program {
  const program = item as unknown as Program

  // Ensure sessions and phases arrays exist
  if (!program.sessions) {
    program.sessions = []
  }
  if (!program.phases) {
    program.phases = []
  }

  // Derive week_number and resolve phase for each session
  program.sessions = program.sessions.map(session => {
    // Parse week number from session.week field
    const weekNum = parseWeekNumber(session.week as string | number | undefined)

    // Resolve phase from the program's phases array based on week number
    const phase = resolvePhase(weekNum, program.phases)

    return {
      ...session,
      week_number: weekNum,
      phase,
      phase_name: phase.name,
    }
  })

  // Sort sessions by date
  program.sessions.sort((a, b) => a.date.localeCompare(b.date))

  return program
}

/**
 * Transform DynamoDB item into a clean Template object.
 */
export function transformTemplate(item: Record<string, unknown>): Template {
  const template = item as unknown as Template
  if (!template.phases) template.phases = []
  if (!template.sessions) template.sessions = []
  if (!template.required_maxes) template.required_maxes = []
  return template
}

/**
 * Transform DynamoDB item into a clean ImportPending object.
 */
export function transformImportPending(item: Record<string, unknown>): ImportPending {
  return item as unknown as ImportPending
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
