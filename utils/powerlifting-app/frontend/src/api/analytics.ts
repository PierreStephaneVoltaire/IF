export interface WeeklyAnalysis {
  week: number
  block: string
  lifts: Record<string, {
    progression_rate_kg_per_week?: number
    volume_change_pct?: number
    intensity_change_pct?: number
    rpe_trend?: string
  }>
  fatigue_index: number | null
  compliance: number | null
  flags: string[]
  projection: {
    total: number
    confidence: number
    weeks_to_comp?: number
    method?: string
  } | null
  projection_reason: string | null
  sessions_analyzed: number
}

import api from './client'

export async function fetchWeeklyAnalysis(weeks = 1): Promise<WeeklyAnalysis> {
  const res = await api.get(`/analytics/analysis/weekly?weeks=${weeks}`)
  const body = res.data
  if (body.error) throw new Error(body.error)
  return body.data
}
