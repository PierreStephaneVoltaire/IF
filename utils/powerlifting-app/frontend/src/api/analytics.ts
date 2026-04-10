import api from './client'

export interface WeeklyAnalysis {
  week: number
  block: string
  lifts: Record<string, {
    progression_rate_kg_per_week?: number | null
    r2?: number | null
    volume_change_pct?: number
    intensity_change_pct?: number
    failed_sets?: number
    rpe_trend?: string
  }>
  fatigue_index: number | null
  fatigue_components: {
    failed_compound_ratio?: number
    fatigue_load_spike?: number
    skip_rate?: number
  } | null
  compliance: {
    phase: string
    planned: number
    completed: number
    pct: number
  } | null
  current_maxes: {
    squat?: number
    bench?: number
    deadlift?: number
    method?: string
  } | null
  estimated_dots: number | null
  projections: Array<{
    total: number
    confidence: number
    weeks_to_comp?: number
    method?: string
    comp_name?: string
  }>
  projection_reason: string | null
  flags: string[]
  sessions_analyzed: number
  exercise_stats: Record<string, {
    total_sets: number
    total_volume: number
    max_kg: number
  }> | null
}

export async function fetchWeeklyAnalysis(weeks = 1, block = 'current'): Promise<WeeklyAnalysis> {
  const res = await api.get(`/analytics/analysis/weekly?weeks=${weeks}&block=${encodeURIComponent(block)}`)
  const body = res.data
  if (body.error) throw new Error(body.error)
  return body.data
}
