import { format, differenceInDays, parseISO, startOfWeek, endOfWeek, isWithinInterval } from 'date-fns'
import type { Session } from '@powerlifting/types'

export const formatDate = (dateStr: string): string =>
  format(parseISO(dateStr), 'EEE MMM d')

export const formatDateLong = (dateStr: string): string =>
  format(parseISO(dateStr), 'EEEE, MMMM d, yyyy')

export const formatDateShort = (dateStr: string): string =>
  format(parseISO(dateStr), 'MMM d')

export const daysUntil = (dateStr: string): number =>
  differenceInDays(parseISO(dateStr), new Date())

export const isToday = (dateStr: string): boolean =>
  format(new Date(), 'yyyy-MM-dd') === dateStr

export const isPast = (dateStr: string): boolean =>
  parseISO(dateStr) < new Date()

export const isFuture = (dateStr: string): boolean =>
  parseISO(dateStr) > new Date()

export const currentProgramWeek = (programStart: string): number => {
  const days = differenceInDays(new Date(), parseISO(programStart))
  return Math.max(1, Math.floor(days / 7) + 1)
}

export const getDayOfWeek = (dateStr: string): string =>
  format(parseISO(dateStr), 'EEEE')

export const getWeekNumber = (dateStr: string, programStart: string): number => {
  const days = differenceInDays(parseISO(dateStr), parseISO(programStart))
  return Math.max(1, Math.floor(days / 7) + 1)
}

export function sessionsThisCalendarWeek(sessions: Session[]): Session[] {
  const now = new Date()
  const weekStart = startOfWeek(now, { weekStartsOn: 0 })
  const weekEnd = endOfWeek(now, { weekStartsOn: 0 })

  return sessions.filter(s => {
    const sessionDate = parseISO(s.date)
    return isWithinInterval(sessionDate, { start: weekStart, end: weekEnd })
  })
}

export function sessionsInDateRange(
  sessions: Session[],
  startDate: string,
  endDate: string
): Session[] {
  return sessions.filter(s => s.date >= startDate && s.date <= endDate)
}

export function groupSessionsByWeek(sessions: Session[]): Map<number, Session[]> {
  const groups = new Map<number, Session[]>()

  for (const session of sessions) {
    const week = session.week_number
    if (!groups.has(week)) {
      groups.set(week, [])
    }
    groups.get(week)!.push(session)
  }

  // Sort sessions within each week by date
  for (const [_, weekSessions] of groups) {
    weekSessions.sort((a, b) => a.date.localeCompare(b.date))
  }

  return groups
}
