// ─── Program Structure ───────────────────────────────────────────────────────

export interface ProgramMeta {
  program_name: string
  program_start: string         // YYYY-MM-DD
  comp_date: string             // YYYY-MM-DD
  federation: string
  practicing_for: string
  version_label: string
  weight_class_kg: number
  weight_class_confirm_by: string
  current_body_weight_kg: number
  current_body_weight_lb: number
  target_squat_kg: number
  target_bench_kg: number
  target_dl_kg: number
  target_total_kg: number
  attempt_pct?: {
    opener: number   // default 0.90
    second: number   // default 0.955
    third: number    // default 1.00
  }
  training_notes: string[]
  change_log: ChangeLogEntry[]
  updated_at: string
  last_comp: LastComp
  height_cm?: number
  arm_wingspan_cm?: number
  leg_length_cm?: number
}

export interface ChangeLogEntry {
  action: string
  source?: string
  date: string
  note?: string
}

export interface LastComp {
  date: string
  body_weight_kg: number
  body_weight_lb: number
  weight_class_kg: number
  results: LiftResults
  past_comp_day_protocol: CompDayProtocol
}

export interface LiftResults {
  squat_kg: number
  bench_kg: number
  deadlift_kg: number
  total_kg: number
}

export interface CompDayProtocol {
  caffeine_total_mg: number
  caffeine_sequence: CaffeineStep[]
  carbs: string
  l_theanine: string
  outcome: string
  notes: string
}

export interface CaffeineStep {
  timing: string
  dose_mg: number
  notes: string
}

// ─── Phase ───────────────────────────────────────────────────────────────────

// Phase is loaded directly from program.phases — never hardcoded in UI logic.
export interface Phase {
  name: string
  intent: string
  start_week: number
  end_week: number
  target_rpe_min?: number
  target_rpe_max?: number
  days_per_week?: number
  notes?: string
}

// ─── Competition ─────────────────────────────────────────────────────────────

export interface Competition {
  name: string
  date: string
  federation: string
  location?: string
  hotel_required?: boolean
  status: 'confirmed' | 'optional' | 'completed' | 'skipped'
  weight_class_kg: number
  body_weight_kg?: number  // Actual weigh-in weight for completed competitions
  targets?: LiftResults    // For upcoming competitions
  results?: LiftResults    // For completed competitions
  notes?: string
  decision_date?: string | null
  between_comp_plan?: BetweenCompPlan
  comp_day_protocol?: CompDayProtocol
}

export interface BetweenCompPlan {
  rest: string
  ramp_back: string
  diet: string
  weight_class: string
  inflammation: string
}

// ─── Session & Exercise ───────────────────────────────────────────────────────

export interface Exercise {
  name: string
  sets: number
  reps: number
  kg: number | null
  notes: string
  failed?: boolean          // deprecated — kept for backwards compat
  failed_sets?: boolean[]   // per-set: [false, false, true, false] = set 3 failed
}

export interface PlannedExercise {
  name: string
  sets: number
  reps: number
  kg: number | null
}

export type SessionStatus = 'planned' | 'logged' | 'completed' | 'skipped'

export interface Session {
  id?: string
  date: string              // YYYY-MM-DD
  day: string               // 'Friday' etc
  week: string              // 'W1 (Warmup)' — raw label from DynamoDB
  week_number: number       // parsed integer, derived on load by backend transform
  phase: Phase              // resolved from program.phases on load by backend transform
  block?: string            // Training block identifier. Default: "current". Archived blocks get user-chosen names.
  status?: SessionStatus
  completed: boolean
  planned_exercises?: PlannedExercise[]
  exercises: Exercise[]
  session_notes: string
  session_rpe: number | null
  body_weight_kg: number | null
  videos?: SessionVideo[]   // Optional video attachments
  pain_log?: unknown[]
}

// ─── Session Video ───────────────────────────────────────────────────────────

export interface SessionVideo {
  video_id: string
  s3_key: string
  thumbnail_s3_key?: string
  video_url: string
  thumbnail_url?: string
  exercise_name?: string
  set_number?: number
  notes?: string
  uploaded_at: string
  thumbnail_status?: 'pending' | 'ready' | 'failed'
}

// ─── Video Library ─────────────────────────────────────────────────────────────

export interface VideoLibraryItem {
  video: SessionVideo
  session_date: string
  day: string
  week_number: number
  phase_name: string
  exercise_sets: number
  exercise_reps: number
  exercise_kg: number | null
}

export interface VideoLibraryResponse {
  videos: VideoLibraryItem[]
  exercises: string[]
}

// ─── Full Program ─────────────────────────────────────────────────────────────

export interface Program {
  pk: string
  sk: string
  meta: ProgramMeta
  phases: Phase[]
  sessions: Session[]
  competitions: Competition[]
  diet_notes: DietNote[]
  supplements: Supplement[]
  supplement_phases: SupplementPhase[]
  lift_profiles?: LiftProfile[]
}

export interface DietNote {
  date: string
  notes: string
  avg_daily_calories?: number
  avg_protein_g?: number
  avg_carb_g?: number
  avg_fat_g?: number
  avg_sleep_hours?: number
  water_intake?: number
  water_unit?: 'litres' | 'cups'
  consistent?: boolean
}

// ─── Lift Profile ─────────────────────────────────────────────────────────────

export interface LiftProfile {
  lift: 'squat' | 'bench' | 'deadlift'
  style_notes: string         // free-form technique/setup description
  sticking_points: string     // where in the lift they struggle most
  primary_muscle: string      // e.g. "quad dominant", "tricep dominant"
  volume_tolerance: 'low' | 'moderate' | 'high'
}

export interface Supplement {
  name: string
  dose: string
}

export interface SupplementPhase {
  phase: number
  phase_name: string
  notes: string
  items: (Supplement & { notes?: string })[]
  peak_week_protocol?: Record<string, string>  // Dynamic key-value pairs (caffeine, creatine_timing, etc.)
  block?: string          // Training block identifier. Default: "current"
  start_week?: number     // Week range start (from block's sessions)
  end_week?: number       // Week range end (from block's sessions)
}

// ─── Max History ─────────────────────────────────────────────────────────────

export interface MaxEntry {
  date: string
  squat_kg: number | null
  bench_kg: number | null
  deadlift_kg: number | null
  total_kg: number | null
  bodyweight_kg: number | null
  context: string
}

// ─── Body Weight Log ─────────────────────────────────────────────────────────

export interface WeightEntry {
  date: string
  kg: number
}

// ─── Glossary ─────────────────────────────────────────────────────────────────

export type MuscleGroup =
  | 'quads' | 'hamstrings' | 'glutes' | 'calves' | 'hip_flexors'
  | 'chest' | 'triceps' | 'front_delts' | 'side_delts' | 'rear_delts'
  | 'lats' | 'traps' | 'rhomboids' | 'teres_major'
  | 'biceps' | 'forearms'
  | 'erectors' | 'lower_back' | 'core' | 'obliques'

export type ExerciseCategory =
  | 'squat' | 'bench' | 'deadlift'
  | 'back' | 'chest' | 'arm' | 'legs' | 'core' | 'lower_back'

export type Equipment =
  | 'barbell' | 'dumbbell' | 'cable' | 'machine'
  | 'bodyweight' | 'hex_bar' | 'bands' | 'kettlebell'

export type FatigueCategory = 'primary_axial' | 'primary_upper' | 'secondary' | 'accessory'

export interface FatigueProfile {
  axial: number       // 0.0-1.0, spinal compression loading
  neural: number      // 0.0-1.0, CNS demand baseline
  peripheral: number  // 0.0-1.0, local muscle damage potential
  systemic: number    // 0.0-1.0, cardiovascular/metabolic demand
}

export type FatigueProfileSource = 'ai_estimated' | 'manual'

export interface GlossaryExercise {
  id: string
  name: string
  category: ExerciseCategory
  fatigue_category: FatigueCategory
  primary_muscles: MuscleGroup[]
  secondary_muscles: MuscleGroup[]
  equipment: Equipment
  cues: string[]
  notes: string
  video_url?: string
  fatigue_profile?: FatigueProfile
  fatigue_profile_source?: FatigueProfileSource
  fatigue_profile_reasoning?: string | null
}

// ─── Plate Calculator ─────────────────────────────────────────────────────────

export type PlateUnit = 'kg' | 'lb'

export interface PlateLoadout {
  plates: number[]          // one side, descending order
  totalKg: number
  perSideKg: number
  remainder: number         // leftover that could not be loaded (should be ~0)
  achievable: boolean
}

// ─── DOTS ─────────────────────────────────────────────────────────────────────

export type Sex = 'male' | 'female'

export interface DotsResult {
  dots: number
  total_kg: number
  bodyweight_kg: number
  sex: Sex
}

// ─── API Response Wrappers ────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T
  error?: string
}

export interface ProgramListItem {
  version: string           // 'v001' or 'current'
  sk: string                // 'program#v001'
  comp_date: string
  updated_at: string
  version_label: string
  is_current?: boolean      // true if this is the current/active version
}

// ─── Glossary Store Item ──────────────────────────────────────────────────────

export interface GlossaryStore {
  pk: string
  sk: string
  exercises: GlossaryExercise[]
  updated_at: string
}

// ─── Max History Store Item ───────────────────────────────────────────────────

export interface MaxHistoryStore {
  pk: string
  sk: string
  entries: MaxEntry[]
  updated_at: string
}

// ─── Weight Log Store Item ────────────────────────────────────────────────────

export interface WeightLogStore {
  pk: string
  sk: string
  entries: WeightEntry[]
  updated_at: string
}
