// ─── Signal Types ─────────────────────────────────────────────────────────────

export type SignalTrend =
  | 'improving_fast'
  | 'improving_slow'
  | 'stable'
  | 'declining_slow'
  | 'declining_fast'

export type LifeLoad = 'low' | 'moderate' | 'high'
export type SocialBattery = 'depleted' | 'low' | 'moderate' | 'high'

export interface DiarySignal {
  pk: string
  sk: string // signal#<ISO8601> or signal#latest
  score: number // 0-10
  trend: SignalTrend
  themes: string[] // e.g., ["work pressure", "sleep"]
  life_load: LifeLoad
  social_battery: SocialBattery
  note: string // Agent-generated 1-sentence summary
  computed_at: string // ISO8601
  entry_count_used: number // How many entries were analyzed
}

// ─── Entry Types (for backend use - never exposed to frontend) ────────────────

export interface DiaryEntry {
  pk: string
  sk: string // entry#<ISO8601>
  content: string
  created_at: string
  expires_at: number // Unix timestamp for TTL
}

// ─── API Response Types ────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T
  error?: string
}

export interface EntryCountResponse {
  count: number
}

export interface WriteEntryResponse {
  ok: true
  entry_count: number
}

// ─── Chart Data Types ──────────────────────────────────────────────────────────

export interface SignalChartDataPoint {
  date: string
  score: number
  trend: SignalTrend
  themes: string[]
  life_load: LifeLoad
  social_battery: SocialBattery
  note: string
}
