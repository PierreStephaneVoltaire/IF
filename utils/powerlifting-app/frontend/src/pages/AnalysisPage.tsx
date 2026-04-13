import { useState, useEffect, useMemo, Fragment } from 'react'
import {
  Activity, Download, AlertTriangle, CheckCircle, TrendingUp, Dumbbell, Trophy,
  Scale, Table as TableIcon, BarChart3, Utensils, Moon, Beef, Brain, RefreshCw, Ruler,
} from 'lucide-react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  fetchWeeklyAnalysis, fetchCorrelationReport, fetchProgramEvaluation,
  type WeeklyAnalysis, type CorrelationReport, type ProgramEvaluationReport,
} from '@/api/analytics'
import { useProgramStore } from '@/store/programStore'
import { fetchWeightLog, fetchGlossary } from '@/api/client'
import { normalizeExerciseName } from '@/utils/volume'
import { FORMULA_DESCRIPTIONS } from '@/constants/formulaDescriptions'
import { updateMetaField } from '@/api/client'
import type { WeightEntry, GlossaryExercise, Competition, ExerciseCategory, LiftProfile } from '@powerlifting/types'
import {
  Stack, Group, Paper, SimpleGrid, Text, Title, Badge, Table,
  Button, ActionIcon, NumberInput, Divider, Loader, Box, Center,
  Select, Progress, Accordion, SegmentedControl, TextInput,
} from '@mantine/core'

// ─── DOTS calculation (male coefficients) ─────────────────────────────────────
const DOTS_A = -307.75076, DOTS_B = 24.0900756, DOTS_C = -0.1918759221
const DOTS_D = 0.0007391293, DOTS_E = -0.000001093

function calcDotsScore(totalKg: number, bwKg: number): number {
  if (bwKg <= 0 || totalKg <= 0) return 0
  const denom = DOTS_A + DOTS_B * bwKg + DOTS_C * bwKg ** 2 + DOTS_D * bwKg ** 3 + DOTS_E * bwKg ** 4
  if (denom <= 0) return 0
  return Math.round((totalKg * 500 / denom) * 100) / 100
}

function epleyE1rm(kg: number, reps: number): number {
  if (reps <= 0 || kg <= 0) return 0
  if (reps === 1) return kg
  return kg * (1 + reps / 30)
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fatigueBadgeColor(score: number | null): string {
  if (score === null) return 'gray'
  if (score >= 0.6) return 'red'
  if (score >= 0.3) return 'yellow'
  return 'green'
}

function fatigueLabel(score: number | null): string {
  if (score === null) return 'N/A'
  if (score >= 0.6) return 'High'
  if (score >= 0.3) return 'Moderate'
  return 'Low'
}

function complianceBadgeColor(pct: number | null): string {
  if (pct === null) return 'gray'
  if (pct >= 80) return 'green'
  if (pct >= 50) return 'yellow'
  return 'red'
}

function rpeTrendIcon(trend?: string) {
  if (!trend) return null
  if (trend === 'up') return <Text span size="xs" fw={500} c="red">&#9650; rising</Text>
  if (trend === 'down') return <Text span size="xs" fw={500} c="green">&#9660; improving</Text>
  return <Text span size="xs" fw={500} c="dimmed">&#9644; stable</Text>
}

function compStatusBadge(status: string) {
  const colors: Record<string, string> = {
    confirmed: 'green',
    optional: 'blue',
    completed: 'gray',
    skipped: 'gray',
  }
  return <Badge variant="light" color={colors[status] || 'gray'} size="sm">{status}</Badge>
}

const CHART_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1',
]

const CORR_DIR_BADGE: Record<string, string> = {
  positive: 'green',
  negative: 'red',
  unclear: 'gray',
}

const CORR_STRENGTH_BADGE: Record<string, string> = {
  strong: 'violet',
  moderate: 'blue',
  weak: 'gray',
}

const LIFT_LABELS: Record<string, string> = { squat: 'Squat', bench: 'Bench', deadlift: 'Deadlift' }

// ─── Main component ────────────────────────────────────────────────────────────

export default function AnalysisPage() {
  const { program, version } = useProgramStore()

  // "block" means all data from program start to now
  const [weeksMode, setWeeksMode] = useState<number | 'block'>(4)
  const [data, setData] = useState<WeeklyAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [weightLog, setWeightLog] = useState<WeightEntry[]>([])
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [viewMode, setViewMode] = useState<'raw' | 'graph'>('raw')
  const [expandedLifts, setExpandedLifts] = useState<Set<string>>(new Set())
  // Attempt % stored as raw strings so users can freely edit
  const [attemptPctRaw, setAttemptPctRaw] = useState({ opener: '0.90', second: '0.955', third: '1.00' })
  const [attemptPctErrors, setAttemptPctErrors] = useState<{ opener: string | null; second: string | null; third: string | null }>({ opener: null, second: null, third: null })
  const [attemptPct, setAttemptPct] = useState({ opener: 0.90, second: 0.955, third: 1.00 })
  const [savingAttempt, setSavingAttempt] = useState(false)

  // Correlation report state
  const [corrReport, setCorrReport] = useState<CorrelationReport | null>(null)
  const [corrLoading, setCorrLoading] = useState(false)
  const [corrError, setCorrError] = useState<string | null>(null)

  // Program evaluation state (full block only)
  const [evalReport, setEvalReport] = useState<ProgramEvaluationReport | null>(null)
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

  // Compute effective weeks from program start when in block mode
  const effectiveWeeks = useMemo(() => {
    if (weeksMode !== 'block') return weeksMode
    const start = program?.meta?.program_start
    if (!start) return 52
    const startDate = new Date(start)
    const today = new Date()
    const diffDays = Math.max(0, (today.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24))
    return Math.max(1, Math.ceil(diffDays / 7))
  }, [weeksMode, program?.meta?.program_start])

  const competitions = useMemo(() => {
    return (program?.competitions || []).sort((a, b) => a.date.localeCompare(b.date))
  }, [program?.competitions])

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchWeeklyAnalysis(effectiveWeeks, 'current')
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [effectiveWeeks])

  useEffect(() => {
    fetchWeightLog(version).then(setWeightLog).catch(console.error)
    fetchGlossary().then(setGlossary).catch(console.error)
  }, [version])

  // Fetch correlation report when weeks >= 4
  useEffect(() => {
    if (effectiveWeeks < 4) {
      setCorrReport(null)
      return
    }
    setCorrLoading(true)
    setCorrError(null)
    fetchCorrelationReport(effectiveWeeks, 'current')
      .then(setCorrReport)
      .catch((e) => setCorrError(e.message))
      .finally(() => setCorrLoading(false))
  }, [effectiveWeeks])

  // Debounced attempt pct validation, save, and re-fetch of attempt selection
  useEffect(() => {
    const timer = setTimeout(() => {
      const keys: Array<'opener' | 'second' | 'third'> = ['opener', 'second', 'third']
      const newErrors = { opener: null as string | null, second: null as string | null, third: null as string | null }
      const newNums = { ...attemptPct }
      let allValid = true
      for (const key of keys) {
        const raw = attemptPctRaw[key]
        const v = parseFloat(raw)
        if (raw === '' || isNaN(v) || v < 0 || v > 1) {
          newErrors[key] = 'Enter a value between 0 and 1 (e.g. 0.90)'
          allValid = false
        } else {
          newErrors[key] = null
          newNums[key] = v
        }
      }
      setAttemptPctErrors(newErrors)
      if (allValid) {
        setAttemptPct(newNums)
        setSavingAttempt(true)
        updateMetaField(version, 'attempt_pct', newNums)
          .then(() => {
            // Re-fetch weekly analysis so attempt_selection reflects new percentages
            return fetchWeeklyAnalysis(effectiveWeeks, 'current').then(setData)
          })
          .finally(() => setSavingAttempt(false))
      }
    }, 400)
    return () => clearTimeout(timer)
  }, [attemptPctRaw])

  // Program evaluation — fetch when in Full Block mode
  useEffect(() => {
    if (weeksMode !== 'block') {
      setEvalReport(null)
      setEvalError(null)
      return
    }
    const completedCount = program?.sessions?.filter(s => (s.block ?? 'current') === 'current' && s.completed).length ?? 0
    if (completedCount < 4) {
      setEvalReport(null)
      return
    }
    setEvalLoading(true)
    setEvalError(null)
    fetchProgramEvaluation(false)
      .then(setEvalReport)
      .catch((e) => setEvalError(e.message))
      .finally(() => setEvalLoading(false))
  }, [weeksMode, program?.meta?.program_start])

  const refreshEvaluation = () => {
    if (weeksMode !== 'block') return
    setEvalLoading(true)
    setEvalError(null)
    setEvalReport(null)
    fetchProgramEvaluation(true)
      .then(setEvalReport)
      .catch((e) => setEvalError(e.message))
      .finally(() => setEvalLoading(false))
  }

  const refreshCorrelation = () => {
    if (effectiveWeeks < 4) return
    setCorrLoading(true)
    setCorrError(null)
    setCorrReport(null)
    // Pass refresh=true by calling the API directly
    import('@/api/analytics').then(({ fetchCorrelationReport }) => {
      const apiBase = import.meta.env.VITE_API_BASE_URL || '/fitness/api'
      fetch(`${apiBase}/analytics/correlation?weeks=${effectiveWeeks}&block=current&refresh=true`)
        .then(r => r.json())
        .then(body => {
          if (body.error) throw new Error(body.error)
          setCorrReport(body.data)
        })
        .catch((e) => setCorrError(e.message))
        .finally(() => setCorrLoading(false))
    })
  }

  // Filtered sessions respecting effective weeks filter
  const filteredSessions = useMemo(() => {
    if (!program?.sessions) return []
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - effectiveWeeks * 7)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return program.sessions.filter(s =>
      (s.block ?? 'current') === 'current' &&
      s.completed &&
      s.date >= cutoffStr
    )
  }, [program?.sessions, effectiveWeeks])

  // Glossary lookups
  const glossaryMuscles = useMemo(() => {
    const lookup = new Map<string, { primary: string[]; secondary: string[] }>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), {
        primary: ex.primary_muscles,
        secondary: ex.secondary_muscles,
      })
    }
    return lookup
  }, [glossary])

  const glossaryCategory = useMemo(() => {
    const lookup = new Map<string, ExerciseCategory>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), ex.category)
    }
    return lookup
  }, [glossary])

  // Muscle group sets aggregation
  const muscleGroupSets = useMemo(() => {
    if (!glossaryMuscles.size || !filteredSessions.length) return {}
    const mgSets: Record<string, number> = {}
    for (const s of filteredSessions) {
      for (const ex of s.exercises || []) {
        const muscles = glossaryMuscles.get(normalizeExerciseName(ex.name))
        if (!muscles) continue
        const sets = ex.sets || 0
        for (const m of muscles.primary) mgSets[m] = (mgSets[m] || 0) + sets
        for (const m of muscles.secondary) mgSets[m] = (mgSets[m] || 0) + sets * 0.5
      }
    }
    return mgSets
  }, [glossaryMuscles, filteredSessions])

  // Muscle group volume aggregation
  const muscleGroupVolume = useMemo(() => {
    if (!glossaryMuscles.size || !filteredSessions.length) return {}
    const mgVol: Record<string, number> = {}
    for (const s of filteredSessions) {
      for (const ex of s.exercises || []) {
        const muscles = glossaryMuscles.get(normalizeExerciseName(ex.name))
        if (!muscles) continue
        const vol = (ex.sets || 0) * (ex.reps || 0) * (ex.kg || 0)
        for (const m of muscles.primary) mgVol[m] = (mgVol[m] || 0) + vol
        for (const m of muscles.secondary) mgVol[m] = (mgVol[m] || 0) + vol * 0.5
      }
    }
    return mgVol
  }, [glossaryMuscles, filteredSessions])

  // Avg per week: muscle group
  const muscleGroupAvgWeekly = useMemo(() => {
    if (!glossaryMuscles.size || !filteredSessions.length) return { sets: {}, volume: {} }
    const numWeeks = new Set(filteredSessions.map(s => s.week_number)).size || 1
    const mgSets: Record<string, number> = {}
    const mgVol: Record<string, number> = {}
    for (const s of filteredSessions) {
      for (const ex of s.exercises || []) {
        const muscles = glossaryMuscles.get(normalizeExerciseName(ex.name))
        if (!muscles) continue
        const sets = ex.sets || 0
        const vol = sets * (ex.reps || 0) * (ex.kg || 0)
        for (const m of muscles.primary) { mgSets[m] = (mgSets[m] || 0) + sets; mgVol[m] = (mgVol[m] || 0) + vol }
        for (const m of muscles.secondary) { mgSets[m] = (mgSets[m] || 0) + sets * 0.5; mgVol[m] = (mgVol[m] || 0) + vol * 0.5 }
      }
    }
    const avgSets: Record<string, number> = {}
    const avgVol: Record<string, number> = {}
    for (const m of Object.keys(mgSets)) {
      avgSets[m] = Math.round((mgSets[m] / numWeeks) * 10) / 10
      avgVol[m] = Math.round(mgVol[m] / numWeeks)
    }
    return { sets: avgSets, volume: avgVol }
  }, [glossaryMuscles, filteredSessions])

  // Per-lift details
  const perLiftDetails = useMemo(() => {
    if (!glossaryCategory.size || !filteredSessions.length) return {}
    const numWeeks = new Set(filteredSessions.map(s => s.week_number)).size || 1
    const result: Record<string, { frequency: number; raw_sets: number; accessories: { name: string; sets: number; volume: number }[] }> = {}
    for (const [liftName, category] of [['squat', 'squat'], ['bench', 'bench'], ['deadlift', 'deadlift']] as const) {
      let liftSessions = 0, rawSets = 0
      const accessoryMap: Record<string, { sets: number; volume: number }> = {}
      for (const s of filteredSessions) {
        let hasLift = false
        for (const ex of s.exercises || []) {
          const exLower = ex.name.toLowerCase().trim()
          const info = glossaryCategory.get(normalizeExerciseName(ex.name))
          const isMainLift = exLower === liftName || (liftName === 'bench' && exLower === 'bench press')
          if (isMainLift || (info && info === category)) hasLift = true
          if (isMainLift) rawSets += ex.sets || 0
          if (info && info === category && !isMainLift) {
            const sets = ex.sets || 0
            const vol = sets * (ex.reps || 0) * (ex.kg || 0)
            if (!accessoryMap[ex.name]) accessoryMap[ex.name] = { sets: 0, volume: 0 }
            accessoryMap[ex.name].sets += sets
            accessoryMap[ex.name].volume += vol
          }
        }
        if (hasLift) liftSessions++
      }
      result[liftName] = {
        frequency: Math.round((liftSessions / numWeeks) * 10) / 10,
        raw_sets: rawSets,
        accessories: Object.entries(accessoryMap).map(([name, d]) => ({ name, ...d })).sort((a, b) => b.volume - a.volume),
      }
    }
    return result
  }, [glossaryCategory, filteredSessions])

  const avgSessionsPerWeek = data ? Math.round((data.sessions_analyzed / effectiveWeeks) * 10) / 10 : null

  // Nutrition trend (calories, water, consistency) + Macro trend
  const nutritionTrend = useMemo(() => {
    if (!program?.diet_notes?.length) return null
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - effectiveWeeks * 7)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    const inWindow = program.diet_notes.filter(n => n.date >= cutoffStr).sort((a, b) => a.date.localeCompare(b.date))
    if (!inWindow.length) return null

    const withCalories = inWindow.filter(n => n.avg_daily_calories != null)
    const withWater = inWindow.filter(n => n.water_intake != null)
    const withProtein = inWindow.filter(n => n.avg_protein_g != null)
    const withCarb = inWindow.filter(n => n.avg_carb_g != null)
    const withFat = inWindow.filter(n => n.avg_fat_g != null)
    const withSleep = inWindow.filter(n => n.avg_sleep_hours != null)
    const consistent = inWindow.filter(n => n.consistent).length

    const weeklyMap = new Map<string, { calories: number[]; water: number[]; protein: number[]; carb: number[]; fat: number[]; sleep: number[]; consistent: number; total: number }>()
    for (const note of inWindow) {
      const d = new Date(note.date)
      const day = d.getDay() || 7
      d.setDate(d.getDate() - day + 1)
      const weekKey = d.toISOString().slice(0, 10)
      const bucket = weeklyMap.get(weekKey) || { calories: [], water: [], protein: [], carb: [], fat: [], sleep: [], consistent: 0, total: 0 }
      if (note.avg_daily_calories != null) bucket.calories.push(note.avg_daily_calories)
      if (note.water_intake != null) bucket.water.push(note.water_intake)
      if (note.avg_protein_g != null) bucket.protein.push(note.avg_protein_g)
      if (note.avg_carb_g != null) bucket.carb.push(note.avg_carb_g)
      if (note.avg_fat_g != null) bucket.fat.push(note.avg_fat_g)
      if (note.avg_sleep_hours != null) bucket.sleep.push(note.avg_sleep_hours)
      if (note.consistent) bucket.consistent += 1
      bucket.total += 1
      weeklyMap.set(weekKey, bucket)
    }

    const avg = (arr: number[]) => arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : null

    const weekly = Array.from(weeklyMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([week, b]) => ({
        week,
        calories: avg(b.calories),
        water: avg(b.water),
        protein: avg(b.protein),
        carb: avg(b.carb),
        fat: avg(b.fat),
        sleep: avg(b.sleep),
        consistency: b.total ? Math.round((b.consistent / b.total) * 100) : null,
      }))

    const calcDelta = (key: keyof typeof weekly[0]): number | null => {
      const pts = weekly.filter(w => w[key] != null)
      if (pts.length < 2) return null
      const first = pts[0][key] as number
      const last = pts[pts.length - 1][key] as number
      return Math.round(((last - first) / Math.max(1, pts.length - 1)) * 10) / 10
    }

    return {
      avgCalories: withCalories.length ? Math.round(withCalories.reduce((s, n) => s + (n.avg_daily_calories || 0), 0) / withCalories.length) : null,
      avgWater: withWater.length ? Math.round(withWater.reduce((s, n) => s + (n.water_intake || 0), 0) / withWater.length * 10) / 10 : null,
      avgProtein: withProtein.length ? Math.round(withProtein.reduce((s, n) => s + (n.avg_protein_g || 0), 0) / withProtein.length) : null,
      avgCarb: withCarb.length ? Math.round(withCarb.reduce((s, n) => s + (n.avg_carb_g || 0), 0) / withCarb.length) : null,
      avgFat: withFat.length ? Math.round(withFat.reduce((s, n) => s + (n.avg_fat_g || 0), 0) / withFat.length) : null,
      avgSleep: withSleep.length ? Math.round(withSleep.reduce((s, n) => s + (n.avg_sleep_hours || 0), 0) / withSleep.length * 10) / 10 : null,
      weekly,
      caloriesChangePerWeek: calcDelta('calories'),
      waterChangePerWeek: calcDelta('water'),
      proteinChangePerWeek: calcDelta('protein'),
      carbChangePerWeek: calcDelta('carb'),
      fatChangePerWeek: calcDelta('fat'),
      sleepChangePerWeek: calcDelta('sleep'),
      waterUnit: withWater[0]?.water_unit || 'litres',
      consistencyPct: inWindow.length ? Math.round((consistent / inWindow.length) * 100) : null,
      entries: inWindow.length,
    }
  }, [program?.diet_notes, effectiveWeeks])

  // Weight trend
  const weightTrend = useMemo(() => {
    if (weightLog.length < 2) return null
    const sorted = [...weightLog].sort((a, b) => a.date.localeCompare(b.date))
    const latest = sorted[sorted.length - 1].kg
    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - effectiveWeeks * 7)
    const cutoffStr = cutoffDate.toISOString().slice(0, 10)
    const windowEntries = sorted.filter(e => e.date >= cutoffStr)
    const oldest = windowEntries.length > 0 ? windowEntries[0].kg : sorted[0].kg
    const change = latest - oldest
    return { latest, change, entries: sorted.slice(-8) }
  }, [weightLog, effectiveWeeks])

  // DOTS + e1RM trend per week
  const dotsTrend = useMemo(() => {
    if (!filteredSessions.length) return null
    type WeekData = { squat: number; bench: number; deadlift: number; bw: number }
    const byWeek = new Map<number, WeekData>()

    for (const s of filteredSessions) {
      const wn = s.week_number
      if (!wn) continue
      if (!byWeek.has(wn)) byWeek.set(wn, { squat: 0, bench: 0, deadlift: 0, bw: 0 })
      const w = byWeek.get(wn)!

      // Pick up body weight
      if (s.body_weight_kg && s.body_weight_kg > w.bw) w.bw = s.body_weight_kg

      for (const ex of s.exercises || []) {
        const name = ex.name.toLowerCase()
        const kg = ex.kg || 0
        const reps = ex.reps || 0
        const e1rm = epleyE1rm(kg, reps)
        if (name === 'squat' || (name.includes('squat') && !name.includes('hack') && !name.includes('split')))
          w.squat = Math.max(w.squat, e1rm)
        else if (name === 'bench press' || name === 'bench')
          w.bench = Math.max(w.bench, e1rm)
        else if (name === 'deadlift' || (name.includes('deadlift') && !name.includes('rdl') && !name.includes('romanian')))
          w.deadlift = Math.max(w.deadlift, e1rm)
      }
    }

    // Fill missing bw from weight log near that week
    const sortedLog = [...weightLog].sort((a, b) => a.date.localeCompare(b.date))

    const rows = Array.from(byWeek.entries())
      .sort(([a], [b]) => a - b)
      .map(([wn, d]) => {
        // Fill bw from log if missing
        let bw = d.bw
        if (!bw && sortedLog.length) bw = sortedLog[sortedLog.length - 1].kg

        const total = (d.squat > 0 ? d.squat : 0) + (d.bench > 0 ? d.bench : 0) + (d.deadlift > 0 ? d.deadlift : 0)
        const dots = total > 0 && bw > 0 ? calcDotsScore(total, bw) : null
        return {
          week: wn,
          squat: d.squat > 0 ? Math.round(d.squat * 10) / 10 : null,
          bench: d.bench > 0 ? Math.round(d.bench * 10) / 10 : null,
          deadlift: d.deadlift > 0 ? Math.round(d.deadlift * 10) / 10 : null,
          total: total > 0 ? Math.round(total * 10) / 10 : null,
          dots,
        }
      })
      .filter(r => r.squat || r.bench || r.deadlift)

    if (!rows.length) return null

    const withDots = rows.filter(r => r.dots !== null)
    let dotsChange: number | null = null
    if (withDots.length >= 2) {
      dotsChange = Math.round(((withDots[withDots.length - 1].dots! - withDots[0].dots!) / Math.max(1, withDots.length - 1)) * 100) / 100
    }

    return { rows, dotsChange }
  }, [filteredSessions, weightLog])

  // Highest maxes from dotsTrend
  const highestMaxes = useMemo(() => {
    if (!dotsTrend || !dotsTrend.rows.length) return null
    let squat = 0, bench = 0, deadlift = 0
    for (const r of dotsTrend.rows) {
      if (r.squat && r.squat > squat) squat = r.squat
      if (r.bench && r.bench > bench) bench = r.bench
      if (r.deadlift && r.deadlift > deadlift) deadlift = r.deadlift
    }
    if (!squat && !bench && !deadlift) return null
    
    const total = squat + bench + deadlift
    let bw = weightTrend?.latest || 0
    if (!bw && weightLog.length) bw = weightLog[weightLog.length - 1].kg
    const dots = total > 0 && bw > 0 ? calcDotsScore(total, bw) : null
    
    return { squat: squat || null, bench: bench || null, deadlift: deadlift || null, total, dots }
  }, [dotsTrend, weightTrend, weightLog])

  // Sleep trend (from biometrics)
  const sleepTrend = useMemo(() => {
    const weeks = nutritionTrend?.weekly.filter(w => w.sleep != null) || []
    if (!weeks.length) return null
    const avg = nutritionTrend!.avgSleep
    const delta = nutritionTrend!.sleepChangePerWeek
    return { avg, delta, weekly: weeks }
  }, [nutritionTrend])

  return (
    <Stack gap="lg">
      <Group justify="space-between" wrap="wrap">
        <Title order={2}>Weekly Analysis</Title>
        <Group gap="sm" wrap="wrap">
          <Select
            size="sm"
            value={String(weeksMode)}
            onChange={(val) => val && setWeeksMode(val === 'block' ? 'block' : Number(val))}
            data={[
              { value: '1', label: 'Last 1 week' },
              { value: '2', label: 'Last 2 weeks' },
              { value: '4', label: 'Last 4 weeks' },
              { value: '8', label: 'Last 8 weeks' },
              { value: 'block', label: 'Full Block (W1 → now)' },
            ]}
            w={200}
          />
          <SegmentedControl
            size="xs"
            value={viewMode}
            onChange={(v) => setViewMode(v as 'raw' | 'graph')}
            data={[
              { value: 'raw', label: 'Table' },
              { value: 'graph', label: 'Charts' },
            ]}
          />
          <Button
            component="a"
            href="/fitness/api/export/xlsx"
            download="program_history.xlsx"
            size="sm"
            leftSection={<Download size={16} />}
          >
            Export Excel
          </Button>
        </Group>
      </Group>

      {loading && <Center mih="20vh"><Loader /></Center>}

      {error && (
        <Paper withBorder p="md" style={{ borderColor: 'var(--mantine-color-red-4)' }}>
          <Text c="red">{error}</Text>
        </Paper>
      )}

      {data && !loading && (
        <>
          {/* Top summary cards */}
          <SimpleGrid cols={{ base: 1, sm: 2, xl: 4 }} spacing="md">
            <Paper withBorder p="md">
              <Group gap="xs" mb="xs">
                <Dumbbell size={18} />
                <Text fw={500}>Estimated 1 Rep Maxes</Text>
              </Group>
              {data.current_maxes ? (
                <Stack gap="xs">
                  <SimpleGrid cols={3}>
                    <Stack gap={2} ta="center">
                      <Text fz="xs" c="dimmed">Squat</Text>
                      <Text fz="lg" fw={700}>{data.current_maxes.squat?.toFixed(1) ?? '--'}</Text>
                    </Stack>
                    <Stack gap={2} ta="center">
                      <Text fz="xs" c="dimmed">Bench</Text>
                      <Text fz="lg" fw={700}>{data.current_maxes.bench?.toFixed(1) ?? '--'}</Text>
                    </Stack>
                    <Stack gap={2} ta="center">
                      <Text fz="xs" c="dimmed">Deadlift</Text>
                      <Text fz="lg" fw={700}>{data.current_maxes.deadlift?.toFixed(1) ?? '--'}</Text>
                    </Stack>
                  </SimpleGrid>
                  {data.estimated_dots !== null && (
                    <Text fz="sm" c="dimmed">Est. DOTS: <Text span fw={500} c="var(--mantine-color-text)">{data.estimated_dots.toFixed(2)}</Text></Text>
                  )}
                  {data.current_maxes.method && (
                    <Text fz="xs" c="dimmed">
                      via {data.current_maxes.method === 'comp_results' ? 'competition' : data.current_maxes.method === 'session_estimated' ? 'session data' : data.current_maxes.method}
                    </Text>
                  )}
                </Stack>
              ) : (
                <Text fz="sm" c="dimmed">No max data available</Text>
              )}
            </Paper>

            <Paper withBorder p="md">
              <Group gap="xs" mb="xs">
                <CheckCircle size={18} />
                <Text fw={500}>Compliance</Text>
              </Group>
              {data.compliance ? (
                <Stack gap={2}>
                  <Text fz="2rem" fw={700} c={complianceBadgeColor(data.compliance.pct)}>{data.compliance.pct.toFixed(0)}%</Text>
                  <Text fz="sm" c="dimmed">{data.compliance.completed}/{data.compliance.planned} sessions</Text>
                  <Text fz="xs" c="dimmed">{data.compliance.phase} block</Text>
                  {avgSessionsPerWeek !== null && <Text fz="xs" c="dimmed">Avg {avgSessionsPerWeek} sessions/wk</Text>}
                </Stack>
              ) : <Text fz="sm" c="dimmed">No compliance data</Text>}
            </Paper>

            <Paper withBorder p="md">
              <Group gap="xs" mb="xs">
                <Activity size={18} />
                <Text fw={500}>Fatigue Signal</Text>
              </Group>
              <Stack gap={2}>
                <Text fz="2rem" fw={700} c={fatigueBadgeColor(data.fatigue_index)}>
                  {data.fatigue_index !== null ? (data.fatigue_index * 100).toFixed(0) + '%' : 'N/A'}
                </Text>
                <Text fz="sm" c="dimmed">{fatigueLabel(data.fatigue_index)} risk</Text>
                <Text fz="xs" c="dimmed" lh="lg">
                  Failed compounds: {((data.fatigue_components?.failed_compound_ratio ?? 0) * 100).toFixed(0)}%
                  &middot; Fatigue spike: {((data.fatigue_components?.composite_spike ?? 0) * 100).toFixed(0)}%
                  &middot; RPE stress: {((data.fatigue_components?.rpe_stress ?? 0) * 100).toFixed(0)}%
                </Text>
              </Stack>
            </Paper>

            <Paper withBorder p="md">
              <Group gap="xs" mb="xs">
                <Activity size={18} />
                <Text fw={500}>Readiness</Text>
              </Group>
              {data.readiness_score ? (
                <Stack gap={2}>
                  <Text fz="2rem" fw={700}>{data.readiness_score.score.toFixed(0)}</Text>
                  <Text fz="xs" c="dimmed" lh="lg">
                    Fatigue: {((data.readiness_score.components.fatigue_norm ?? 0) * 100).toFixed(0)}%
                    &middot; RPE drift: {((data.readiness_score.components.rpe_drift ?? 0) * 100).toFixed(0)}%
                    &middot; BW stability: {((data.readiness_score.components.bw_stability ?? 0) * 100).toFixed(0)}%
                    &middot; Miss rate: {((data.readiness_score.components.miss_rate ?? 0) * 100).toFixed(0)}%
                  </Text>
                </Stack>
              ) : <Text fz="sm" c="dimmed">N/A</Text>}
            </Paper>
          </SimpleGrid>

          {/* INOL */}
          {data.inol && data.inol.avg_inol && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">INOL (Window Average)</Text>
              <SimpleGrid cols={3} mb="sm">
                {Object.entries(data.inol.avg_inol).map(([lift, val]) => (
                  <Stack key={lift} gap={2} ta="center" p="sm" style={{ borderRadius: 'var(--mantine-radius-sm)', background: `var(--mantine-color-${val > 4.0 ? 'red' : val < 2.0 ? 'yellow' : 'green'}-light)` }}>
                    <Text fz="xs" c="dimmed" tt="capitalize">{lift}</Text>
                    <Text fz="xl" fw={700} c={val > 4.0 ? 'red' : val < 2.0 ? 'yellow' : 'green'}>{val.toFixed(2)}</Text>
                    <Text fz="xs" c="dimmed">{val > 4.0 ? 'Overreaching' : val < 2.0 ? 'Low stimulus' : 'Productive'}</Text>
                  </Stack>
                ))}
              </SimpleGrid>
              {data.inol.flags.length > 0 && (
                <Group gap="xs" wrap="wrap">
                  {data.inol.flags.map(flag => (
                    <Badge key={flag} color="yellow" variant="light">{flag}</Badge>
                  ))}
                </Group>
              )}
            </Paper>
          )}

          {/* ACWR */}
          {data.acwr && !('status' in data.acwr) && (
            <Paper withBorder p="md">
              <Group justify="space-between" mb="sm">
                <Text fw={500}>ACWR (Acute:Chronic Workload Ratio)</Text>
                <Badge
                  color={(data.acwr as any).composite_zone === 'optimal' ? 'green' : (data.acwr as any).composite_zone === 'caution' ? 'yellow' : (data.acwr as any).composite_zone === 'danger' ? 'red' : 'gray'}
                  variant="light"
                >
                  Composite: {(data.acwr as any).composite?.toFixed(2) ?? 'N/A'} ({(data.acwr as any).composite_zone})
                </Badge>
              </Group>
              <SimpleGrid cols={4} spacing="md">
                {Object.entries((data.acwr as any).dimensions).map(([dim, info]: [string, any]) => {
                  const zoneColor = info.zone === 'optimal' ? 'green' : info.zone === 'caution' ? 'yellow' : info.zone === 'danger' ? 'red' : 'gray'
                  return (
                    <Stack key={dim} gap={2} ta="center" p="sm" style={{ borderRadius: 'var(--mantine-radius-sm)', background: `var(--mantine-color-${zoneColor}-light)` }}>
                      <Text fz="xs" tt="capitalize">{dim}</Text>
                      <Text fz="xl" fw={700}>{info.value?.toFixed(2) ?? '--'}</Text>
                      <Text fz="xs" tt="capitalize">{info.zone}</Text>
                    </Stack>
                  )
                })}
              </SimpleGrid>
            </Paper>
          )}
          {data.acwr && 'status' in data.acwr && (
            <Paper withBorder p="md">
              <Text fw={500} mb="xs">ACWR (Acute:Chronic Workload Ratio)</Text>
              <Text fz="sm" c="dimmed">{(data.acwr as any).reason ?? 'Not enough data yet. Keep logging sessions.'}</Text>
            </Paper>
          )}

          {/* RI Distribution */}
          {data.ri_distribution && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">Relative Intensity Distribution</Text>
              <SimpleGrid cols={3} mb="md">
                {(['heavy', 'moderate', 'light'] as const).map(bucket => {
                  const info = data.ri_distribution!.overall[bucket]
                  const color = bucket === 'heavy' ? 'red' : bucket === 'moderate' ? 'green' : 'blue'
                  return (
                    <Stack key={bucket} gap={2} ta="center" p="sm" style={{ borderRadius: 'var(--mantine-radius-sm)', background: `var(--mantine-color-${color}-light)` }}>
                      <Text fz="xs" tt="capitalize">{bucket}</Text>
                      <Text fz="xl" fw={700}>{info.pct.toFixed(0)}%</Text>
                      <Text fz="xs">{info.count} sets</Text>
                    </Stack>
                  )
                })}
              </SimpleGrid>
              {Object.keys(data.ri_distribution.per_lift).length > 0 && (
                <Box style={{ overflowX: 'auto' }}>
                  <Table fz="sm">
                    <Table.Thead><Table.Tr><Table.Th>Lift</Table.Th><Table.Th ta="right">Heavy %</Table.Th><Table.Th ta="right">Moderate %</Table.Th><Table.Th ta="right">Light %</Table.Th></Table.Tr></Table.Thead>
                    <Table.Tbody>
                      {Object.entries(data.ri_distribution.per_lift).map(([lift, buckets]) => (
                        <Table.Tr key={lift}>
                          <Table.Td fw={500}>{lift}</Table.Td>
                          <Table.Td ta="right" c="red">{buckets.heavy.pct.toFixed(0)}%</Table.Td>
                          <Table.Td ta="right" c="green">{buckets.moderate.pct.toFixed(0)}%</Table.Td>
                          <Table.Td ta="right" c="blue">{buckets.light.pct.toFixed(0)}%</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Box>
              )}
            </Paper>
          )}

          {/* Specificity Ratio */}
          {data.specificity_ratio && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">Specificity Ratio</Text>
              <SimpleGrid cols={2} spacing="md">
                <Stack gap="xs">
                  <Text fz="xs" c="dimmed">Narrow (SBD only)</Text>
                  <Progress value={Math.min(data.specificity_ratio.narrow * 100, 100)} />
                  <Text fz="sm" fw={500}>{(data.specificity_ratio.narrow * 100).toFixed(1)}%</Text>
                </Stack>
                <Stack gap="xs">
                  <Text fz="xs" c="dimmed">Broad (SBD + secondary)</Text>
                  <Progress value={Math.min(data.specificity_ratio.broad * 100, 100)} color="blue" />
                  <Text fz="sm" fw={500}>{(data.specificity_ratio.broad * 100).toFixed(1)}%</Text>
                </Stack>
              </SimpleGrid>
              <Text fz="xs" c="dimmed" mt="sm">{data.specificity_ratio.sbd_sets} SBD sets / {data.specificity_ratio.total_sets} total sets</Text>
            </Paper>
          )}

          {/* Fatigue Dimensions */}
          {data.fatigue_dimensions && Object.keys(data.fatigue_dimensions.weekly).length > 0 && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">Fatigue Dimensions (Weekly)</Text>
              <Box visibleFrom="sm" style={{ overflowX: 'auto' }}>
                <Table fz="sm">
                  <Table.Thead><Table.Tr><Table.Th>Week</Table.Th><Table.Th ta="right">Axial</Table.Th><Table.Th ta="right">Neural</Table.Th><Table.Th ta="right">Peripheral</Table.Th><Table.Th ta="right">Systemic</Table.Th></Table.Tr></Table.Thead>
                  <Table.Tbody>
                    {Object.entries(data.fatigue_dimensions.weekly)
                      .sort(([a], [b]) => Number(a) - Number(b)).slice(-8)
                      .map(([week, dims]) => (
                        <Table.Tr key={week}>
                          <Table.Td fw={500}>W{week}</Table.Td>
                          <Table.Td ta="right">{dims.axial.toFixed(1)}</Table.Td>
                          <Table.Td ta="right">{dims.neural.toFixed(1)}</Table.Td>
                          <Table.Td ta="right">{dims.peripheral.toFixed(1)}</Table.Td>
                          <Table.Td ta="right">{dims.systemic.toFixed(1)}</Table.Td>
                        </Table.Tr>
                      ))}
                  </Table.Tbody>
                </Table>
              </Box>
              <Stack hiddenFrom="sm" gap="xs">
                {Object.entries(data.fatigue_dimensions.weekly)
                  .sort(([a], [b]) => Number(a) - Number(b)).slice(-8)
                  .map(([week, dims]) => (
                    <Paper key={week} p="sm" bg="var(--mantine-color-default-hover)" radius="sm">
                      <Text fw={700} mb={4}>Week {week}</Text>
                      <SimpleGrid cols={4} spacing="xs">
                        <Stack gap={0} ta="center">
                          <Text fz="xs" c="dimmed">Axial</Text>
                          <Text fz="sm" fw={500}>{dims.axial.toFixed(1)}</Text>
                        </Stack>
                        <Stack gap={0} ta="center">
                          <Text fz="xs" c="dimmed">Neural</Text>
                          <Text fz="sm" fw={500}>{dims.neural.toFixed(1)}</Text>
                        </Stack>
                        <Stack gap={0} ta="center">
                          <Text fz="xs" c="dimmed">Periph</Text>
                          <Text fz="sm" fw={500}>{dims.peripheral.toFixed(1)}</Text>
                        </Stack>
                        <Stack gap={0} ta="center">
                          <Text fz="xs" c="dimmed">Systemic</Text>
                          <Text fz="sm" fw={500}>{dims.systemic.toFixed(1)}</Text>
                        </Stack>
                      </SimpleGrid>
                    </Paper>
                  ))}
              </Stack>
            </Paper>
          )}

          {/* Projections */}
          {data.projections.length > 0 ? (
            <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
              {data.projections.map((proj, i) => (
                <Paper key={i} withBorder p="md">
                  <Group gap="xs" mb="xs">
                    <TrendingUp size={18} />
                    <Text fw={500}>{proj.comp_name || 'Projected Total'}</Text>
                  </Group>
                  <Text fz="2rem" fw={700}>{proj.total.toFixed(1)} kg</Text>
                  <Text fz="sm" c="dimmed" mt="xs">
                    Confidence: {(proj.confidence * 100).toFixed(0)}%
                    {proj.weeks_to_comp !== undefined && ` (${proj.weeks_to_comp.toFixed(1)} wks out)`}
                  </Text>
                  {proj.method && <Text fz="xs" c="dimmed">via {proj.method === 'session_estimated' ? 'session e1RM' : proj.method}</Text>}
                </Paper>
              ))}
            </SimpleGrid>
          ) : (
            <Paper withBorder p="md">
              <Group gap="xs" mb="xs">
                <TrendingUp size={18} />
                <Text fw={500}>Projected Total</Text>
              </Group>
              <Text fz="lg" c="dimmed">{data.projection_reason || 'No competition date set'}</Text>
            </Paper>
          )}

          {/* DOTS & e1RM Trend */}
          {dotsTrend && dotsTrend.rows.length >= 2 && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <TrendingUp size={18} />
                <Text fw={500}>e1RM Progression &amp; DOTS Trend</Text>
                {dotsTrend.dotsChange !== null && (
                  <Badge color={dotsTrend.dotsChange >= 0 ? 'green' : 'red'} variant="light" ml="auto">
                    {dotsTrend.dotsChange >= 0 ? '+' : ''}{dotsTrend.dotsChange} DOTS/wk
                  </Badge>
                )}
              </Group>
              <Box style={{ overflowX: 'auto' }}>
                <Table fz="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Week</Table.Th>
                      <Table.Th ta="right">Squat e1RM</Table.Th>
                      <Table.Th ta="right">Bench e1RM</Table.Th>
                      <Table.Th ta="right">DL e1RM</Table.Th>
                      <Table.Th ta="right">Total</Table.Th>
                      <Table.Th ta="right">DOTS</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {dotsTrend.rows.map(r => (
                      <Table.Tr key={r.week}>
                        <Table.Td fw={500}>W{r.week}</Table.Td>
                        <Table.Td ta="right">{r.squat?.toFixed(1) ?? '--'}</Table.Td>
                        <Table.Td ta="right">{r.bench?.toFixed(1) ?? '--'}</Table.Td>
                        <Table.Td ta="right">{r.deadlift?.toFixed(1) ?? '--'}</Table.Td>
                        <Table.Td ta="right" fw={500}>{r.total?.toFixed(1) ?? '--'}</Table.Td>
                        <Table.Td ta="right" fw={700} c="blue">{r.dots?.toFixed(2) ?? '--'}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Box>
              <Text fz="xs" c="dimmed" mt="xs">DOTS calculated from estimated 1RM (Epley) and nearest bodyweight. Male coefficients used.</Text>
            </Paper>
          )}

          {/* Body Weight Trend */}
          {weightTrend && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <Scale size={18} />
                <Text fw={500}>Body Weight Trend</Text>
              </Group>
              <Group align="baseline" gap="md">
                <Text fz="2rem" fw={700}>{weightTrend.latest.toFixed(1)} kg</Text>
                <Text fz="sm" fw={500} c={weightTrend.change >= 0 ? 'yellow' : 'green'}>
                  {weightTrend.change >= 0 ? '+' : ''}{weightTrend.change.toFixed(1)} kg over {effectiveWeeks} wk{effectiveWeeks !== 1 ? 's' : ''}
                </Text>
              </Group>
              <SimpleGrid cols={{ base: 4, md: 8 }} mt="sm">
                {weightTrend.entries.map(e => (
                  <Stack key={e.date} gap={2} ta="center">
                    <Text fz="xs" c="dimmed">{e.date.slice(5)}</Text>
                    <Text fz="sm" fw={500}>{e.kg.toFixed(1)}</Text>
                  </Stack>
                ))}
              </SimpleGrid>
            </Paper>
          )}

          {/* Sleep Trend */}
          {sleepTrend && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <Moon size={18} />
                <Text fw={500}>Sleep Trend</Text>
              </Group>
              <Group align="baseline" gap="md" mb="sm">
                {sleepTrend.avg !== null && <Text fz="2rem" fw={700}>{sleepTrend.avg} hrs/night avg</Text>}
                {sleepTrend.delta !== null && (
                  <Text fz="sm" fw={500} c={sleepTrend.delta >= 0 ? 'green' : 'red'}>
                    {sleepTrend.delta >= 0 ? '+' : ''}{sleepTrend.delta} hrs/wk
                  </Text>
                )}
              </Group>
              <SimpleGrid cols={{ base: 3, sm: 6 }}>
                {sleepTrend.weekly.filter(w => w.sleep != null).map(w => (
                  <Stack key={w.week} gap={2} ta="center" p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                    <Text fz="xs" c="dimmed">{w.week.slice(5)}</Text>
                    <Text fz="sm" fw={700} c={(w.sleep as number) >= 7 ? 'green' : (w.sleep as number) >= 6 ? 'yellow' : 'red'}>
                      {(w.sleep as number).toFixed(1)}h
                    </Text>
                  </Stack>
                ))}
              </SimpleGrid>
              <Text fz="xs" c="dimmed" mt="xs">
                {sleepTrend.avg !== null && sleepTrend.avg >= 7 ? '✓ Meeting 7hr+ target' : '⚠ Below 7hr target — may impact recovery'}
              </Text>
            </Paper>
          )}

          {/* Nutrition Trend */}
          {nutritionTrend && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <Utensils size={18} />
                <Text fw={500}>Nutrition Trend</Text>
              </Group>
              <SimpleGrid cols={{ base: 2, md: 4, lg: 6 }} mb="sm">
                {nutritionTrend.avgCalories !== null && (
                  <Stack gap={2} ta="center">
                    <Text fz="xs" c="dimmed">Avg Calories</Text>
                    <Text fz="lg" fw={700}>{nutritionTrend.avgCalories.toLocaleString()}</Text>
                    {nutritionTrend.caloriesChangePerWeek !== null && (
                      <Text fz="xs" fw={500} c={nutritionTrend.caloriesChangePerWeek >= 0 ? 'yellow' : 'green'}>
                        {nutritionTrend.caloriesChangePerWeek >= 0 ? '+' : ''}{nutritionTrend.caloriesChangePerWeek}/wk
                      </Text>
                    )}
                  </Stack>
                )}
                {nutritionTrend.avgProtein !== null && (
                  <Stack gap={2} ta="center">
                    <Group gap={4} justify="center">
                      <Beef size={12} />
                      <Text fz="xs" c="dimmed">Avg Protein</Text>
                    </Group>
                    <Text fz="lg" fw={700}>{nutritionTrend.avgProtein}g</Text>
                    {nutritionTrend.proteinChangePerWeek !== null && (
                      <Text fz="xs" fw={500} c={nutritionTrend.proteinChangePerWeek >= 0 ? 'green' : 'red'}>
                        {nutritionTrend.proteinChangePerWeek >= 0 ? '+' : ''}{nutritionTrend.proteinChangePerWeek}g/wk
                      </Text>
                    )}
                  </Stack>
                )}
                {nutritionTrend.avgCarb !== null && (
                  <Stack gap={2} ta="center">
                    <Text fz="xs" c="dimmed">Avg Carbs</Text>
                    <Text fz="lg" fw={700}>{nutritionTrend.avgCarb}g</Text>
                    {nutritionTrend.carbChangePerWeek !== null && (
                      <Text fz="xs" fw={500} c={nutritionTrend.carbChangePerWeek >= 0 ? 'yellow' : 'orange'}>
                        {nutritionTrend.carbChangePerWeek >= 0 ? '+' : ''}{nutritionTrend.carbChangePerWeek}g/wk
                      </Text>
                    )}
                  </Stack>
                )}
                {nutritionTrend.avgFat !== null && (
                  <Stack gap={2} ta="center">
                    <Text fz="xs" c="dimmed">Avg Fat</Text>
                    <Text fz="lg" fw={700}>{nutritionTrend.avgFat}g</Text>
                    {nutritionTrend.fatChangePerWeek !== null && (
                      <Text fz="xs" fw={500} c={nutritionTrend.fatChangePerWeek >= 0 ? 'yellow' : 'green'}>
                        {nutritionTrend.fatChangePerWeek >= 0 ? '+' : ''}{nutritionTrend.fatChangePerWeek}g/wk
                      </Text>
                    )}
                  </Stack>
                )}
                {nutritionTrend.avgWater !== null && (
                  <Stack gap={2} ta="center">
                    <Text fz="xs" c="dimmed">Avg Water</Text>
                    <Text fz="lg" fw={700}>{nutritionTrend.avgWater} {nutritionTrend.waterUnit === 'litres' ? 'L' : 'cups'}</Text>
                    {nutritionTrend.waterChangePerWeek !== null && (
                      <Text fz="xs" fw={500} c={nutritionTrend.waterChangePerWeek >= 0 ? 'blue' : 'orange'}>
                        {nutritionTrend.waterChangePerWeek >= 0 ? '+' : ''}{nutritionTrend.waterChangePerWeek}/wk
                      </Text>
                    )}
                  </Stack>
                )}
                {nutritionTrend.consistencyPct !== null && (
                  <Stack gap={2} ta="center">
                    <Text fz="xs" c="dimmed">Consistency</Text>
                    <Text fz="lg" fw={700} c={nutritionTrend.consistencyPct >= 80 ? 'green' : nutritionTrend.consistencyPct >= 50 ? 'yellow' : 'red'}>
                      {nutritionTrend.consistencyPct}%
                    </Text>
                  </Stack>
                )}
              </SimpleGrid>
            </Paper>
          )}

          {/* Athlete Measurements */}
          {(program?.meta?.height_cm || program?.meta?.arm_wingspan_cm || program?.meta?.leg_length_cm) && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <Ruler size={18} />
                <Text fw={500}>Athlete Measurements</Text>
                <Text fz="xs" c="dimmed" ml="auto">Edit on Dashboard</Text>
              </Group>
              <SimpleGrid cols={3} spacing="md">
                {program.meta.height_cm && (
                  <Stack gap={2} ta="center" p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                    <Text fz="xs" c="dimmed">Height</Text>
                    <Text fz="lg" fw={700}>{program.meta.height_cm} cm</Text>
                  </Stack>
                )}
                {program.meta.arm_wingspan_cm && (
                  <Stack gap={2} ta="center" p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                    <Text fz="xs" c="dimmed">Arm Wingspan</Text>
                    <Text fz="lg" fw={700}>{program.meta.arm_wingspan_cm} cm</Text>
                  </Stack>
                )}
                {program.meta.leg_length_cm && (
                  <Stack gap={2} ta="center" p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                    <Text fz="xs" c="dimmed">Leg Length</Text>
                    <Text fz="lg" fw={700}>{program.meta.leg_length_cm} cm</Text>
                  </Stack>
                )}
              </SimpleGrid>
            </Paper>
          )}

          {program?.lift_profiles && program.lift_profiles.length > 0 && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <Dumbbell size={18} />
                <Text fw={500}>Lift Style Profiles</Text>
                <Text fz="xs" c="dimmed" ml="auto">Edit on Dashboard</Text>
              </Group>
              <SimpleGrid cols={{ base: 1, lg: 3 }}>
                {program.lift_profiles.map((profile) => (
                  <Stack key={profile.lift} gap="xs" p="sm" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                    <Text fw={500} fz="sm" tt="capitalize" pb="xs" style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}>
                      {LIFT_LABELS[profile.lift] || profile.lift}
                    </Text>
                    {profile.style_notes && (
                      <Stack gap={2}>
                        <Text fz="xs" c="dimmed">Style &amp; Setup</Text>
                        <Text fz="xs" lh="lg">{profile.style_notes}</Text>
                      </Stack>
                    )}
                    {profile.sticking_points && (
                      <Stack gap={2}>
                        <Text fz="xs" c="dimmed">Sticking Points</Text>
                        <Text fz="xs" lh="lg" c="orange">{profile.sticking_points}</Text>
                      </Stack>
                    )}
                    {profile.primary_muscle && (
                      <Stack gap={2}>
                        <Text fz="xs" c="dimmed">Primary Driver</Text>
                        <Text fz="xs" fw={500}>{profile.primary_muscle}</Text>
                      </Stack>
                    )}
                    <Badge
                      color={profile.volume_tolerance === 'low' ? 'red' : profile.volume_tolerance === 'moderate' ? 'yellow' : 'green'}
                      variant="light"
                      tt="capitalize"
                    >
                      {profile.volume_tolerance} volume tolerance
                    </Badge>
                  </Stack>
                ))}
              </SimpleGrid>
            </Paper>
          )}

          {/* Competitions */}
          {competitions.length > 0 && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <Trophy size={18} />
                <Text fw={500}>Competitions</Text>
              </Group>
              <Box style={{ overflowX: 'auto' }}>
                <Table fz="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Name</Table.Th>
                      <Table.Th>Date</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th ta="right">Squat</Table.Th>
                      <Table.Th ta="right">Bench</Table.Th>
                      <Table.Th ta="right">Deadlift</Table.Th>
                      <Table.Th ta="right">Total</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {competitions.map(c => (
                      <Table.Tr key={c.date + c.name}>
                        <Table.Td fw={500}>{c.name}</Table.Td>
                        <Table.Td c="dimmed">{c.date}</Table.Td>
                        <Table.Td>{compStatusBadge(c.status)}</Table.Td>
                        {c.results ? (
                          <>
                            <Table.Td ta="right">{c.results.squat_kg.toFixed(1)}</Table.Td>
                            <Table.Td ta="right">{c.results.bench_kg.toFixed(1)}</Table.Td>
                            <Table.Td ta="right">{c.results.deadlift_kg.toFixed(1)}</Table.Td>
                            <Table.Td ta="right" fw={700}>{c.results.total_kg.toFixed(1)}</Table.Td>
                          </>
                        ) : (
                          <Table.Td ta="right" c="dimmed" colSpan={4}>--</Table.Td>
                        )}
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Box>
            </Paper>
          )}

          {/* Per-lift breakdown */}
          {Object.keys(data.lifts).length > 0 && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">Per-Lift Breakdown</Text>
              <Box style={{ overflowX: 'auto' }}>
                <Table fz="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Exercise</Table.Th>
                      <Table.Th ta="right">Freq</Table.Th>
                      <Table.Th ta="right">Sets</Table.Th>
                      <Table.Th ta="right">Progression</Table.Th>
                      <Table.Th ta="right">R&sup2;</Table.Th>
                      <Table.Th ta="right">Volume %</Table.Th>
                      <Table.Th ta="right">Intensity %</Table.Th>
                      <Table.Th ta="right">Failed</Table.Th>
                      <Table.Th ta="right">RPE Trend</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {Object.entries(data.lifts).map(([name, lift]) => {
                      const liftKey = name.toLowerCase().replace(' press', '')
                      const details = perLiftDetails[liftKey]
                      const isExpanded = expandedLifts.has(name)
                      return (
                        <Fragment key={name}>
                          <Table.Tr>
                            <Table.Td fw={500}>
                              <Group gap="xs">
                                {name}
                                {details && details.accessories.length > 0 && (
                                  <Button
                                    variant="subtle"
                                    size="compact-xs"
                                    color="gray"
                                    onClick={() => setExpandedLifts(prev => {
                                      const next = new Set(prev)
                                      if (next.has(name)) next.delete(name); else next.add(name)
                                      return next
                                    })}
                                  >
                                    {isExpanded ? '▼' : '▶'} {details.accessories.length} acc
                                  </Button>
                                )}
                              </Group>
                            </Table.Td>
                            <Table.Td ta="right">{details ? <Text span fz="sm">{details.frequency}/wk</Text> : <Text span fz="sm" c="dimmed">--</Text>}</Table.Td>
                            <Table.Td ta="right">{details ? <Text span fz="sm">{details.raw_sets}</Text> : <Text span fz="sm" c="dimmed">--</Text>}</Table.Td>
                            <Table.Td ta="right">
                              {lift.progression_rate_kg_per_week !== undefined && lift.progression_rate_kg_per_week !== null
                                ? <Text span fz="sm" c={lift.progression_rate_kg_per_week >= 0 ? 'green' : 'red'}>{lift.progression_rate_kg_per_week >= 0 ? '+' : ''}{lift.progression_rate_kg_per_week.toFixed(1)} kg/wk</Text>
                                : <Text span fz="sm" c="dimmed">--</Text>}
                            </Table.Td>
                            <Table.Td ta="right">
                              {lift.r2 !== undefined && lift.r2 !== null
                                ? <Text span fz="sm" c="dimmed">{(lift.r2 * 100).toFixed(0)}%</Text>
                                : <Text span fz="sm" c="dimmed">--</Text>}
                            </Table.Td>
                            <Table.Td ta="right">
                              {lift.volume_change_pct !== undefined
                                ? <Text span fz="sm" c={lift.volume_change_pct >= 0 ? 'green' : 'red'}>{lift.volume_change_pct >= 0 ? '+' : ''}{lift.volume_change_pct.toFixed(0)}%</Text>
                                : <Text span fz="sm" c="dimmed">--</Text>}
                            </Table.Td>
                            <Table.Td ta="right">
                              {lift.intensity_change_pct !== undefined
                                ? <Text span fz="sm" c={lift.intensity_change_pct >= 0 ? 'green' : 'red'}>{lift.intensity_change_pct >= 0 ? '+' : ''}{lift.intensity_change_pct.toFixed(0)}%</Text>
                                : <Text span fz="sm" c="dimmed">--</Text>}
                            </Table.Td>
                            <Table.Td ta="right">
                              {lift.failed_sets !== undefined && lift.failed_sets > 0
                                ? <Badge variant="light" color="red" size="sm">{lift.failed_sets}</Badge>
                                : <Text span fz="sm" c="dimmed">0</Text>}
                            </Table.Td>
                            <Table.Td ta="right">{rpeTrendIcon(lift.rpe_trend) || <Text span fz="sm" c="dimmed">--</Text>}</Table.Td>
                          </Table.Tr>
                          {isExpanded && details && details.accessories.length > 0 && (
                            <Table.Tr>
                              <Table.Td colSpan={9}>
                                <Box ml="md">
                                  <Text fz="xs" c="dimmed" mb="xs">Accessory / Secondary Work</Text>
                                  <SimpleGrid cols={{ base: 2, md: 3, lg: 4 }}>
                                    {details.accessories.map(a => (
                                      <Box key={a.name} p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default)' }}>
                                        <Text fz="xs" fw={500}>{a.name}</Text>
                                        <Text fz="xs" c="dimmed">{a.sets} sets · {Math.round(a.volume).toLocaleString()} kg</Text>
                                      </Box>
                                    ))}
                                  </SimpleGrid>
                                </Box>
                              </Table.Td>
                            </Table.Tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </Table.Tbody>
                </Table>
              </Box>
            </Paper>
          )}

          {/* Exercise Stats */}
          {data.exercise_stats && Object.keys(data.exercise_stats).length > 0 && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">Exercise Volume</Text>
              {viewMode === 'raw' ? (
                <Box style={{ overflowX: 'auto' }}>
                  <Table fz="sm">
                    <Table.Thead><Table.Tr><Table.Th>Exercise</Table.Th><Table.Th ta="right">Total Sets</Table.Th><Table.Th ta="right">Volume (kg)</Table.Th><Table.Th ta="right">Max (kg)</Table.Th></Table.Tr></Table.Thead>
                    <Table.Tbody>
                      {Object.entries(data.exercise_stats)
                        .sort((a, b) => b[1].total_volume - a[1].total_volume)
                        .map(([name, s]) => (
                          <Table.Tr key={name}>
                            <Table.Td fw={500}>{name}</Table.Td>
                            <Table.Td ta="right">{s.total_sets}</Table.Td>
                            <Table.Td ta="right">{s.total_volume.toLocaleString()}</Table.Td>
                            <Table.Td ta="right">{s.max_kg.toFixed(1)}</Table.Td>
                          </Table.Tr>
                        ))}
                    </Table.Tbody>
                  </Table>
                </Box>
              ) : (
                <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
                  <Box>
                    <Text fz="xs" c="dimmed" ta="center" mb="xs">Sets Distribution</Text>
                    <ResponsiveContainer width="100%" height={350}>
                      <PieChart>
                        <Pie data={Object.entries(data.exercise_stats).sort((a, b) => b[1].total_sets - a[1].total_sets).slice(0, 10).map(([name, s], i) => ({ name, value: s.total_sets, fill: CHART_COLORS[i % CHART_COLORS.length] }))} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
                          {Object.entries(data.exercise_stats).sort((a, b) => b[1].total_sets - a[1].total_sets).slice(0, 10).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </Box>
                  <Box>
                    <Text fz="xs" c="dimmed" ta="center" mb="xs">Volume Distribution</Text>
                    <ResponsiveContainer width="100%" height={350}>
                      <PieChart>
                        <Pie data={Object.entries(data.exercise_stats).sort((a, b) => b[1].total_volume - a[1].total_volume).slice(0, 10).map(([name, s], i) => ({ name, value: s.total_volume, fill: CHART_COLORS[i % CHART_COLORS.length] }))} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
                          {Object.entries(data.exercise_stats).sort((a, b) => b[1].total_volume - a[1].total_volume).slice(0, 10).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </Box>
                  <Box>
                    <Text fz="xs" c="dimmed" ta="center" mb="xs">Max Weight (kg)</Text>
                    <ResponsiveContainer width="100%" height={350}>
                      <BarChart data={Object.entries(data.exercise_stats).sort((a, b) => b[1].max_kg - a[1].max_kg).slice(0, 10).map(([name, s], i) => ({ name, max_kg: s.max_kg, fill: CHART_COLORS[i % CHART_COLORS.length] }))} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" /><YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} />
                        <Tooltip />
                        <Bar dataKey="max_kg" radius={[0, 4, 4, 0]}>
                          {Object.entries(data.exercise_stats).sort((a, b) => b[1].max_kg - a[1].max_kg).slice(0, 10).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Box>
                </SimpleGrid>
              )}
            </Paper>
          )}

          {/* Muscle Group Sets */}
          {Object.keys(muscleGroupSets).length > 0 && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">Sets by Muscle Group</Text>
              {viewMode === 'raw' ? (
                <SimpleGrid cols={{ base: 2, md: 4, lg: 5 }}>
                  {Object.entries(muscleGroupSets).sort((a, b) => b[1] - a[1]).map(([muscle, sets]) => (
                    <Stack key={muscle} gap={2} ta="center" p="xs" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                      <Text fz="xs" c="dimmed" tt="capitalize">{muscle.replace(/_/g, ' ')}</Text>
                      <Text fz="lg" fw={700}>{Math.round(sets)}</Text>
                    </Stack>
                  ))}
                </SimpleGrid>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={Object.entries(muscleGroupSets).sort((a, b) => b[1] - a[1]).map(([name, value], i) => ({ name: name.replace(/_/g, ' '), value, fill: CHART_COLORS[i % CHART_COLORS.length] }))} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}>
                      {Object.entries(muscleGroupSets).sort((a, b) => b[1] - a[1]).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </Paper>
          )}

          {/* Avg Weekly by Muscle Group */}
          {Object.keys(muscleGroupAvgWeekly.sets).length > 0 && (
            <Paper withBorder p="md">
              <Text fw={500} mb="sm">Avg Weekly by Muscle Group</Text>
              {viewMode === 'raw' ? (
                <Box style={{ overflowX: 'auto' }}>
                  <Table fz="sm">
                    <Table.Thead><Table.Tr><Table.Th>Muscle Group</Table.Th><Table.Th ta="right">Avg Sets/wk</Table.Th><Table.Th ta="right">Avg Vol/wk (kg)</Table.Th></Table.Tr></Table.Thead>
                    <Table.Tbody>
                      {Object.entries(muscleGroupAvgWeekly.sets).sort((a, b) => (muscleGroupAvgWeekly.volume[b[0]] || 0) - (muscleGroupAvgWeekly.volume[a[0]] || 0)).map(([muscle, sets]) => (
                        <Table.Tr key={muscle}>
                          <Table.Td fw={500}>{muscle.replace(/_/g, ' ')}</Table.Td>
                          <Table.Td ta="right">{sets}</Table.Td>
                          <Table.Td ta="right">{(muscleGroupAvgWeekly.volume[muscle] || 0).toLocaleString()}</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Box>
              ) : (
                <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                  <Box>
                    <Text fz="xs" c="dimmed" ta="center" mb="xs">Avg Sets/wk</Text>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={Object.entries(muscleGroupAvgWeekly.sets).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name: name.replace(/_/g, ' '), 'Avg Sets/wk': value }))}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                        <YAxis /><Tooltip />
                        <Bar dataKey="Avg Sets/wk" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Box>
                  <Box>
                    <Text fz="xs" c="dimmed" ta="center" mb="xs">Avg Vol/wk (kg)</Text>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={Object.entries(muscleGroupAvgWeekly.volume).sort((a, b) => b[1] - a[1]).map(([name, value]) => ({ name: name.replace(/_/g, ' '), 'Avg Vol/wk': value }))}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                        <YAxis /><Tooltip />
                        <Bar dataKey="Avg Vol/wk" fill="#22c55e" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Box>
                </SimpleGrid>
              )}
            </Paper>
          )}

          {/* ─── Exercise ROI Correlation ───────────────────────────────────────── */}
          <Paper withBorder p="md">
            <Group justify="space-between" mb="sm">
              <Group gap="xs">
                <Brain size={18} />
                <Text fw={500}>Exercise ROI Correlation</Text>
                {corrReport && (
                  <Badge color={corrReport.cached ? 'blue' : 'green'} variant="light" size="sm">
                    {corrReport.cached ? `Cached ${corrReport.generated_at ? new Date(corrReport.generated_at).toLocaleDateString() : ''}` : 'Just generated'}
                  </Badge>
                )}
              </Group>
              {effectiveWeeks >= 4 && (
                <Button
                  variant="subtle"
                  size="xs"
                  onClick={refreshCorrelation}
                  disabled={corrLoading}
                  leftSection={<RefreshCw size={14} style={corrLoading ? { animation: 'spin 1s linear infinite' } : undefined} />}
                >
                  Regenerate
                </Button>
              )}
            </Group>

            {effectiveWeeks < 4 ? (
              <Text size="sm" c="dimmed">Correlation analysis requires at least 4 weeks of data. Select 4+ weeks or Full Block.</Text>
            ) : corrLoading ? (
              <Group gap="xs" py="md">
                <Loader size="xs" />
                <Text size="sm" c="dimmed">Analyzing training data with AI...</Text>
              </Group>
            ) : corrError ? (
              <Text size="sm" c="red">{corrError}</Text>
            ) : corrReport ? (
              <>
                {corrReport.insufficient_data ? (
                  <Text size="sm" c="dimmed">{corrReport.insufficient_data_reason || 'Insufficient data for meaningful correlation analysis.'}</Text>
                ) : (
                  <>
                    {corrReport.summary && (
                      <Text size="sm" c="dimmed" mb="md" p="sm" fs="italic" style={{ background: 'var(--mantine-color-default-hover)', borderRadius: 'var(--mantine-radius-sm)' }}>{corrReport.summary}</Text>
                    )}
                    {corrReport.findings.length > 0 ? (
                      <Box style={{ overflowX: 'auto' }}>
                        <Table fz="sm">
                          <Table.Thead>
                            <Table.Tr>
                              <Table.Th ta="left">Exercise</Table.Th>
                              <Table.Th ta="left">→ Lift</Table.Th>
                              <Table.Th ta="left">Direction</Table.Th>
                              <Table.Th ta="left">Strength</Table.Th>
                              <Table.Th ta="left">Reasoning</Table.Th>
                              <Table.Th ta="left">Caveat</Table.Th>
                            </Table.Tr>
                          </Table.Thead>
                          <Table.Tbody>
                            {corrReport.findings.map((f, i) => (
                              <Table.Tr key={i} style={{ verticalAlign: 'top' }}>
                                <Table.Td fw={500}>{f.exercise}</Table.Td>
                                <Table.Td>{f.lift}</Table.Td>
                                <Table.Td>
                                  <Badge size="xs" variant="light" color={CORR_DIR_BADGE[f.correlation_direction] || 'gray'} style={{ textTransform: 'capitalize' }}>
                                    {f.correlation_direction}
                                  </Badge>
                                </Table.Td>
                                <Table.Td>
                                  <Badge size="xs" variant="light" color={CORR_STRENGTH_BADGE[f.strength] || 'gray'} style={{ textTransform: 'capitalize' }}>
                                    {f.strength}
                                  </Badge>
                                </Table.Td>
                                <Table.Td fz="xs">{f.reasoning}</Table.Td>
                                <Table.Td c="dimmed" fz="xs" fs="italic">{f.caveat}</Table.Td>
                              </Table.Tr>
                            ))}
                          </Table.Tbody>
                        </Table>
                      </Box>
                    ) : (
                      <Text size="sm" c="dimmed">No significant anatomically-relevant correlations found in this window.</Text>
                    )}
                  </>
                )}
              </>
            ) : null}
          </Paper>

          {/* ─── Program Evaluation (Full Block only) ──────────────────────────── */}
          {weeksMode === 'block' && (() => {
            const completedCount = program?.sessions?.filter(s => (s.block ?? 'current') === 'current' && s.completed).length ?? 0
            const STANCE_COLORS: Record<string, string> = { continue: 'green', monitor: 'blue', adjust: 'yellow', critical: 'red' }
            const ALIGN_COLORS: Record<string, string> = { good: 'green', mixed: 'yellow', poor: 'red' }
            const PRIORITY_COLORS: Record<string, string> = { low: 'gray', moderate: 'yellow', high: 'red' }
            return (
              <Paper withBorder p="md">
                <Group justify="space-between" mb="sm">
                  <Group gap="xs">
                    <Trophy size={18} />
                    <Text fw={500}>Program Evaluation</Text>
                    {evalReport && (
                      <Badge color={evalReport.cached ? 'blue' : 'green'} variant="light" size="sm">
                        {evalReport.cached ? `Cached ${evalReport.generated_at ? new Date(evalReport.generated_at).toLocaleDateString() : ''}` : 'Just generated'}
                      </Badge>
                    )}
                    {evalReport?.stance && (
                      <Badge color={STANCE_COLORS[evalReport.stance] || 'gray'} variant="light" size="sm" style={{ textTransform: 'capitalize' }}>
                        {evalReport.stance}
                      </Badge>
                    )}
                  </Group>
                  <Button
                    variant="subtle"
                    size="xs"
                    onClick={refreshEvaluation}
                    disabled={evalLoading || completedCount < 4}
                    leftSection={<RefreshCw size={14} style={evalLoading ? { animation: 'spin 1s linear infinite' } : undefined} />}
                  >
                    Regenerate
                  </Button>
                </Group>

                {completedCount < 4 ? (
                  <Text size="sm" c="dimmed">Program evaluation requires at least 4 completed sessions in the current block. Complete more sessions and return here.</Text>
                ) : evalLoading ? (
                  <Group gap="xs" py="md">
                    <Loader size="xs" />
                    <Text size="sm" c="dimmed">Evaluating your training block with AI sports scientist...</Text>
                  </Group>
                ) : evalError ? (
                  <Text size="sm" c="red">{evalError}</Text>
                ) : evalReport ? (
                  <>
                    {evalReport.insufficient_data ? (
                      <Text size="sm" c="dimmed">{evalReport.insufficient_data_reason || 'Insufficient data for program evaluation.'}</Text>
                    ) : (
                      <Stack gap="md">
                        {evalReport.summary && (
                          <Text size="sm" c="dimmed" p="sm" fs="italic" style={{ background: 'var(--mantine-color-default-hover)', borderRadius: 'var(--mantine-radius-sm)' }}>{evalReport.summary}</Text>
                        )}

                        {evalReport.competition_alignment.length > 0 && (
                          <Stack gap="xs">
                            <Text size="sm" fw={500}>Competition Alignment</Text>
                            <Stack gap="xs">
                              {evalReport.competition_alignment.map((ca, i) => (
                                <Group key={i} gap="sm" align="flex-start" p="xs" style={{ background: 'var(--mantine-color-default-hover)', borderRadius: 'var(--mantine-radius-sm)' }}>
                                  <Badge color={ALIGN_COLORS[ca.alignment] || 'gray'} variant="light" size="sm" style={{ textTransform: 'capitalize', marginTop: 2 }}>{ca.alignment}</Badge>
                                  <Stack gap={2}>
                                    <Text size="sm" fw={500}>{ca.competition} <Text span size="xs" c="dimmed">({ca.role}{ca.weeks_to_comp != null ? `, ${ca.weeks_to_comp.toFixed(1)} wks out` : ''})</Text></Text>
                                    <Text size="xs" c="dimmed">{ca.reason}</Text>
                                  </Stack>
                                </Group>
                              ))}
                            </Stack>
                          </Stack>
                        )}

                        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                          {evalReport.what_is_working.length > 0 && (
                            <Stack gap="xs">
                              <Text size="sm" fw={500} c="green">What's Working</Text>
                              <Stack gap={4}>
                                {evalReport.what_is_working.map((item, i) => (
                                  <Group key={i} gap="xs" align="flex-start" wrap="nowrap">
                                    <Badge variant="light" color="green" size="sm">✓</Badge>
                                    <Text size="xs">{item}</Text>
                                  </Group>
                                ))}
                              </Stack>
                            </Stack>
                          )}
                          {evalReport.what_is_not_working.length > 0 && (
                            <Stack gap="xs">
                              <Text size="sm" fw={500} c="red">Needs Attention</Text>
                              <Stack gap={4}>
                                {evalReport.what_is_not_working.map((item, i) => (
                                  <Group key={i} gap="xs" align="flex-start" wrap="nowrap">
                                    <Badge variant="light" color="red" size="sm">✗</Badge>
                                    <Text size="xs">{item}</Text>
                                  </Group>
                                ))}
                              </Stack>
                            </Stack>
                          )}
                        </SimpleGrid>

                        {evalReport.small_changes.length > 0 && (
                          <Stack gap="xs">
                            <Text size="sm" fw={500}>Suggested Adjustments</Text>
                            <Stack gap="xs">
                              {evalReport.small_changes.map((sc, i) => (
                                <Paper key={i} withBorder p="sm">
                                  <Group gap="xs" mb={4}>
                                    <Badge color={PRIORITY_COLORS[sc.priority] || 'gray'} variant="light" size="sm" style={{ textTransform: 'capitalize' }}>{sc.priority}</Badge>
                                    <Text size="sm" fw={500}>{sc.change}</Text>
                                  </Group>
                                  <Text size="xs" c="dimmed">{sc.why}</Text>
                                  {sc.risk && <Text size="xs" c="orange" mt={4}>Risk: {sc.risk}</Text>}
                                </Paper>
                              ))}
                            </Stack>
                          </Stack>
                        )}

                        {evalReport.monitoring_focus.length > 0 && (
                          <Stack gap="xs">
                            <Text size="sm" fw={500}>Monitor Closely</Text>
                            <Group gap="xs" wrap="wrap">
                              {evalReport.monitoring_focus.map((item, i) => (
                                <Badge key={i} color="blue" variant="light">{item}</Badge>
                              ))}
                            </Group>
                          </Stack>
                        )}

                        {evalReport.conclusion && (
                          <Text size="sm" fw={500} pt="sm" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>{evalReport.conclusion}</Text>
                        )}
                      </Stack>
                    )}
                  </>
                ) : null}
              </Paper>
            )
          })()}

          {/* Formula Reference */}
          <Accordion mt="xl" variant="separated">
            <Accordion.Item value="formulas-outer">
              <Accordion.Control>
                <Text size="sm" fw={500} c="dimmed">How These Numbers Are Calculated</Text>
              </Accordion.Control>
              <Accordion.Panel>
                <Accordion variant="contained">
                  {FORMULA_DESCRIPTIONS.map(formula => (
                    <Accordion.Item key={formula.id} value={formula.id}>
                      <Accordion.Control>
                        <Text size="sm" fw={500}>{formula.title}</Text>
                      </Accordion.Control>
                      <Accordion.Panel>
                        <Stack gap="xs">
                          <Text size="sm">{formula.summary}</Text>
                          <Box component="pre" fz="xs" p="sm" style={{ background: 'var(--mantine-color-dark-8, #1a1b1e)', borderRadius: 'var(--mantine-radius-sm)', overflowX: 'auto', fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{formula.formula}</Box>
                          {formula.variables && (
                            <SimpleGrid cols={2} spacing="xs">
                              {formula.variables.map(v => (
                                <Text key={v.name} size="xs"><Text span ff="monospace">{v.name}</Text>: {v.description}</Text>
                              ))}
                            </SimpleGrid>
                          )}
                          {formula.thresholds && (
                            <Table fz="xs" mt="xs">
                              <Table.Thead><Table.Tr><Table.Th ta="left">Condition</Table.Th><Table.Th ta="left">Value</Table.Th><Table.Th ta="left">Flag</Table.Th></Table.Tr></Table.Thead>
                              <Table.Tbody>{formula.thresholds.map(t => <Table.Tr key={t.label}><Table.Td>{t.label}</Table.Td><Table.Td>{t.value}</Table.Td><Table.Td>{t.flag || '—'}</Table.Td></Table.Tr>)}</Table.Tbody>
                            </Table>
                          )}
                        </Stack>
                      </Accordion.Panel>
                    </Accordion.Item>
                  ))}
                </Accordion>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>

          {/* Flags */}
          {data.flags.length > 0 && (
            <Paper withBorder p="md">
              <Group gap="xs" mb="sm">
                <AlertTriangle size={18} color="var(--mantine-color-yellow-5)" />
                <Text fw={500}>Flags</Text>
              </Group>
              <Group gap="xs" wrap="wrap">
                {data.flags.map(flag => (
                  <Badge key={flag} color="yellow" variant="light">{flag}</Badge>
                ))}
              </Group>
            </Paper>
          )}

          {/* Footer */}
          <Text size="xs" c="dimmed">
            Week {data.week} ({data.block}) &middot; {data.sessions_analyzed} sessions analyzed
            {weeksMode === 'block' && ` · Full block (${effectiveWeeks} wks)`}
          </Text>
        </>
      )}

      {!data && !loading && !error && (
        <Center mih="20vh">
          <Text c="dimmed">No analysis data available for the selected period.</Text>
        </Center>
      )}
    </Stack>
  )
}
