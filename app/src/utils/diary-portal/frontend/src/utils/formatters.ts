import { format, formatDistanceToNow, parseISO } from 'date-fns'
import type { SignalTrend, LifeLoad, SocialBattery } from '@diary-portal/types'

/**
 * Format ISO date string to readable date
 */
export function formatDate(isoString: string): string {
  return format(parseISO(isoString), 'MMM d, yyyy')
}

/**
 * Format ISO date string to readable date and time
 */
export function formatDateTime(isoString: string): string {
  return format(parseISO(isoString), 'MMM d, yyyy h:mm a')
}

/**
 * Format ISO date string to relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(isoString: string): string {
  return formatDistanceToNow(parseISO(isoString), { addSuffix: true })
}

/**
 * Format score with one decimal place
 */
export function formatScore(score: number): string {
  return score.toFixed(1)
}

/**
 * Get color class based on score
 */
export function getScoreColor(score: number): string {
  if (score >= 7) return 'text-green-500'
  if (score >= 5) return 'text-yellow-500'
  return 'text-red-500'
}

/**
 * Get background color class based on score
 */
export function getScoreBgColor(score: number): string {
  if (score >= 7) return 'bg-green-500/20'
  if (score >= 5) return 'bg-yellow-500/20'
  return 'bg-red-500/20'
}

/**
 * Format trend as human-readable text
 */
export function formatTrend(trend: SignalTrend): string {
  const trendMap: Record<SignalTrend, string> = {
    improving_fast: 'Improving fast',
    improving_slow: 'Improving slowly',
    stable: 'Stable',
    declining_slow: 'Declining slowly',
    declining_fast: 'Declining fast',
  }
  return trendMap[trend]
}

/**
 * Get trend arrow icon
 */
export function getTrendArrow(trend: SignalTrend): string {
  const arrowMap: Record<SignalTrend, string> = {
    improving_fast: '↑↑',
    improving_slow: '↑',
    stable: '→',
    declining_slow: '↓',
    declining_fast: '↓↓',
  }
  return arrowMap[trend]
}

/**
 * Get trend color class
 */
export function getTrendColor(trend: SignalTrend): string {
  if (trend === 'improving_fast' || trend === 'improving_slow') {
    return 'text-green-500'
  }
  if (trend === 'stable') {
    return 'text-gray-400'
  }
  return 'text-red-500'
}

/**
 * Format life load as human-readable text
 */
export function formatLifeLoad(load: LifeLoad): string {
  const loadMap: Record<LifeLoad, string> = {
    low: 'Low',
    moderate: 'Moderate',
    high: 'High',
  }
  return loadMap[load]
}

/**
 * Get life load color class
 */
export function getLifeLoadColor(load: LifeLoad): string {
  const colorMap: Record<LifeLoad, string> = {
    low: 'text-green-400',
    moderate: 'text-yellow-400',
    high: 'text-red-400',
  }
  return colorMap[load]
}

/**
 * Format social battery as human-readable text
 */
export function formatSocialBattery(battery: SocialBattery): string {
  const batteryMap: Record<SocialBattery, string> = {
    depleted: 'Depleted',
    low: 'Low',
    moderate: 'Moderate',
    high: 'High',
  }
  return batteryMap[battery]
}

/**
 * Get social battery color class
 */
export function getSocialBatteryColor(battery: SocialBattery): string {
  const colorMap: Record<SocialBattery, string> = {
    depleted: 'text-red-400',
    low: 'text-yellow-400',
    moderate: 'text-blue-400',
    high: 'text-green-400',
  }
  return colorMap[battery]
}
