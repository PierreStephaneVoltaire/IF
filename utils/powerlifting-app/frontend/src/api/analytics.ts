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
    composite_spike?: number
    /** RPE stress = clamp((avg_session_rpe - 6.0) / 4.0, 0, 1). Replaces skip_rate. */
    rpe_stress?: number
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
  deload_info?: {
    deload_weeks: number[]
    break_weeks: number[]
    effective_training_weeks: number
  }
  inol?: {
    per_lift_per_week: Record<string, Record<string, number>>
    /** Average INOL per lift across the analysis window. */
    avg_inol: Record<string, number>
    raw_per_lift_per_week?: Record<string, Record<string, number>>
    /** Average unadjusted INOL before lift-specific stimulus coefficients. */
    raw_avg_inol?: Record<string, number>
    stimulus_coefficients?: Record<string, number>
    flags: string[]
  } | null
  acwr?: {
    composite: number
    composite_zone: string
    dimensions: Record<string, { value: number; zone: string }>
  } | { status: 'insufficient_data'; reason: string } | null
  ri_distribution?: {
    overall: Record<string, { count: number; pct: number }>
    per_lift: Record<string, Record<string, { count: number; pct: number }>>
  }
  specificity_ratio?: {
    narrow: number
    broad: number
    total_sets: number
    sbd_sets: number
  }
  readiness_score?: {
    score: number
    zone: string
    components: Record<string, number>
  }
  fatigue_dimensions?: {
    weekly: Record<string, { axial: number; neural: number; peripheral: number; systemic: number }>
    acwr: Record<string, any>
    spike: Record<string, any>
  }
  attempt_selection?: Record<string, {
    opener: number
    second: number
    third: number
  }> & { total?: number; attempt_pct_used?: { opener: number; second: number; third: number } }
}

export interface CorrelationFinding {
  exercise: string
  lift: 'squat' | 'bench' | 'deadlift'
  correlation_direction: 'positive' | 'negative' | 'unclear'
  strength: 'strong' | 'moderate' | 'weak'
  reasoning: string
  caveat: string
}

export interface CorrelationReport {
  findings: CorrelationFinding[]
  summary: string
  generated_at: string
  window_start: string
  weeks: number
  cached: boolean
  insufficient_data?: boolean
  insufficient_data_reason?: string
}

export async function fetchWeeklyAnalysis(weeks = 1, block = 'current'): Promise<WeeklyAnalysis> {
  const res = await api.get(`/analytics/analysis/weekly?weeks=${weeks}&block=${encodeURIComponent(block)}`)
  const body = res.data
  if (body.error) throw new Error(body.error)
  return body.data
}

export async function fetchCorrelationReport(weeks: number, block = 'current'): Promise<CorrelationReport> {
  const res = await api.get(`/analytics/correlation?weeks=${weeks}&block=${encodeURIComponent(block)}`)
  const body = res.data
  if (body.error) throw new Error(body.error)
  return body.data
}

export interface ProgramEvaluationSmallChange {
  change: string
  why: string
  risk: string
  priority: 'low' | 'moderate' | 'high'
}

export interface ProgramEvaluationCompAlignment {
  competition: string
  role: 'primary' | 'practice'
  weeks_to_comp?: number | null
  alignment: 'good' | 'mixed' | 'poor'
  reason: string
}

export interface ProgramEvaluationReport {
  stance: 'continue' | 'monitor' | 'adjust' | 'critical'
  summary: string
  what_is_working: string[]
  what_is_not_working: string[]
  competition_alignment: ProgramEvaluationCompAlignment[]
  small_changes: ProgramEvaluationSmallChange[]
  monitoring_focus: string[]
  conclusion: string
  insufficient_data?: boolean
  insufficient_data_reason?: string
  generated_at: string
  window_start: string
  weeks: number
  cached: boolean
}

export async function fetchProgramEvaluation(refresh = false): Promise<ProgramEvaluationReport> {
  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api'
  const res = await fetch(`${apiBase}/analytics/program-evaluation?refresh=${refresh}`, {
    headers: { 'Content-Type': 'application/json' },
  })
  const body = await res.json()
  if (body.error) throw new Error(body.error)
  return body.data
}
