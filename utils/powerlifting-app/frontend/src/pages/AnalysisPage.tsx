import { useState, useEffect, useMemo, Fragment } from 'react'
import { Activity, Download, AlertTriangle, CheckCircle, TrendingUp, Dumbbell, Trophy, Scale, Table as TableIcon, BarChart3, Utensils } from 'lucide-react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { fetchWeeklyAnalysis, type WeeklyAnalysis } from '@/api/analytics'
import { useProgramStore } from '@/store/programStore'
import { fetchWeightLog, fetchGlossary } from '@/api/client'
import { normalizeExerciseName } from '@/utils/volume'
import { FORMULA_DESCRIPTIONS } from '@/constants/formulaDescriptions'
import { updateMetaField } from '@/api/client'
import type { WeightEntry, GlossaryExercise, Competition, ExerciseCategory } from '@powerlifting/types'

function fatigueColor(score: number | null): string {
  if (score === null) return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
  if (score >= 0.6) return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  if (score >= 0.3) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
  return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
}

function fatigueLabel(score: number | null): string {
  if (score === null) return 'N/A'
  if (score >= 0.6) return 'High'
  if (score >= 0.3) return 'Moderate'
  return 'Low'
}

function complianceColor(pct: number | null): string {
  if (pct === null) return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
  if (pct >= 80) return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
  if (pct >= 50) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
  return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
}

function rpeTrendIcon(trend?: string) {
  if (!trend) return null
  if (trend === 'up') return <span className="text-red-500 text-xs font-medium">&#9650; rising</span>
  if (trend === 'down') return <span className="text-green-500 text-xs font-medium">&#9660; improving</span>
  return <span className="text-gray-500 text-xs font-medium">&#9644; stable</span>
}

function compStatusBadge(status: string) {
  const styles: Record<string, string> = {
    confirmed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    optional: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    completed: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    skipped: 'bg-gray-100 text-gray-400',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${styles[status] || 'bg-gray-100 text-gray-500'}`}>
      {status}
    </span>
  )
}

const CHART_COLORS = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1']

export default function AnalysisPage() {
  const { program, version } = useProgramStore()
  const [weeks, setWeeks] = useState(4)
  const [data, setData] = useState<WeeklyAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [weightLog, setWeightLog] = useState<WeightEntry[]>([])
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [viewMode, setViewMode] = useState<'raw' | 'graph'>('raw')
  const [expandedLifts, setExpandedLifts] = useState<Set<string>>(new Set())
  const [attemptPct, setAttemptPct] = useState({ opener: 0.90, second: 0.955, third: 1.00 })
  const [savingAttempt, setSavingAttempt] = useState(false)

  const competitions = useMemo(() => {
    return (program?.competitions || []).sort((a, b) => a.date.localeCompare(b.date))
  }, [program?.competitions])

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchWeeklyAnalysis(weeks, 'current')
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [weeks])

  useEffect(() => {
    fetchWeightLog(version).then(setWeightLog).catch(console.error)
    fetchGlossary().then(setGlossary).catch(console.error)
  }, [version])

  useEffect(() => {
    const metaPct = program?.meta?.attempt_pct
    if (metaPct) {
      setAttemptPct({ opener: metaPct.opener, second: metaPct.second, third: metaPct.third })
    }
  }, [program?.meta?.attempt_pct])

  // Fix 1: Shared filtered sessions respecting weeks filter
  const filteredSessions = useMemo(() => {
    if (!program?.sessions) return []
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - weeks * 7)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return program.sessions.filter(s =>
      (s.block ?? 'current') === 'current' &&
      s.completed &&
      s.date >= cutoffStr
    )
  }, [program?.sessions, weeks])

  // Glossary lookups (shared across memos)
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
        for (const m of muscles.primary) {
          mgSets[m] = (mgSets[m] || 0) + sets
          mgVol[m] = (mgVol[m] || 0) + vol
        }
        for (const m of muscles.secondary) {
          mgSets[m] = (mgSets[m] || 0) + sets * 0.5
          mgVol[m] = (mgVol[m] || 0) + vol * 0.5
        }
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

  // Fix 2: Per-lift details — frequency counts any exercise in same category
  const perLiftDetails = useMemo(() => {
    if (!glossaryCategory.size || !filteredSessions.length) return {}
    const numWeeks = new Set(filteredSessions.map(s => s.week_number)).size || 1

    const result: Record<string, { frequency: number; raw_sets: number; accessories: { name: string; sets: number; volume: number }[] }> = {}

    for (const [liftName, category] of [['squat', 'squat'], ['bench', 'bench'], ['deadlift', 'deadlift']] as const) {
      let liftSessions = 0
      let rawSets = 0
      const accessoryMap: Record<string, { sets: number; volume: number }> = {}

      for (const s of filteredSessions) {
        let hasLift = false
        for (const ex of s.exercises || []) {
          const exLower = ex.name.toLowerCase().trim()
          const info = glossaryCategory.get(normalizeExerciseName(ex.name))
          const isMainLift = exLower === liftName || (liftName === 'bench' && exLower === 'bench press')
          if (isMainLift || (info && info === category)) {
            hasLift = true
          }
          if (isMainLift) {
            rawSets += ex.sets || 0
          }
          // Accessory work: same category but not the main lift itself
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
        accessories: Object.entries(accessoryMap)
          .map(([name, data]) => ({ name, ...data }))
          .sort((a, b) => b.volume - a.volume),
      }
    }
    return result
  }, [glossaryCategory, filteredSessions])

  // Avg sessions per week
  const avgSessionsPerWeek = data ? Math.round((data.sessions_analyzed / weeks) * 10) / 10 : null

  // Fix 3: Nutrition trend with +/- per week deltas
  const nutritionTrend = useMemo(() => {
    if (!program?.diet_notes?.length) return null
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - weeks * 7)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    const inWindow = program.diet_notes
      .filter(n => n.date >= cutoffStr)
      .sort((a, b) => a.date.localeCompare(b.date))
    if (!inWindow.length) return null

    const withCalories = inWindow.filter((n) => n.avg_daily_calories != null)
    const withWater = inWindow.filter((n) => n.water_intake != null)
    const consistent = inWindow.filter((n) => n.consistent).length

    const weeklyMap = new Map<string, { calories: number[]; water: number[]; consistent: number; total: number }>()
    for (const note of inWindow) {
      const d = new Date(note.date)
      const day = d.getDay() || 7
      d.setDate(d.getDate() - day + 1)
      const weekKey = d.toISOString().slice(0, 10)
      const bucket = weeklyMap.get(weekKey) || { calories: [], water: [], consistent: 0, total: 0 }
      if (note.avg_daily_calories != null) bucket.calories.push(note.avg_daily_calories)
      if (note.water_intake != null) bucket.water.push(note.water_intake)
      if (note.consistent) bucket.consistent += 1
      bucket.total += 1
      weeklyMap.set(weekKey, bucket)
    }

    const weekly = Array.from(weeklyMap.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([week, bucket]) => ({
        week,
        calories: bucket.calories.length ? bucket.calories.reduce((s, v) => s + v, 0) / bucket.calories.length : null,
        water: bucket.water.length ? bucket.water.reduce((s, v) => s + v, 0) / bucket.water.length : null,
        consistency: bucket.total ? Math.round((bucket.consistent / bucket.total) * 100) : null,
      }))

    let caloriesChangePerWeek: number | null = null
    if (weekly.filter(w => w.calories != null).length >= 2) {
      const first = weekly.find(w => w.calories != null)!
      const last = [...weekly].reverse().find(w => w.calories != null)!
      caloriesChangePerWeek = Math.round((last.calories! - first.calories!) / Math.max(1, weekly.length - 1))
    }

    let waterChangePerWeek: number | null = null
    if (weekly.filter(w => w.water != null).length >= 2) {
      const first = weekly.find(w => w.water != null)!
      const last = [...weekly].reverse().find(w => w.water != null)!
      waterChangePerWeek = Math.round(((last.water! - first.water!) / Math.max(1, weekly.length - 1)) * 10) / 10
    }

    return {
      avgCalories: withCalories.length ? Math.round(withCalories.reduce((s, n) => s + (n.avg_daily_calories || 0), 0) / withCalories.length) : null,
      caloriesChangePerWeek,
      avgWater: withWater.length ? Math.round(withWater.reduce((s, n) => s + (n.water_intake || 0), 0) / withWater.length * 10) / 10 : null,
      weekly,
      waterChangePerWeek,
      waterUnit: withWater[0]?.water_unit || 'litres',
      consistencyPct: inWindow.length ? Math.round((consistent / inWindow.length) * 100) : null,
      entries: inWindow.length,
    }
  }, [program?.diet_notes, weeks])

  // Weight trend
  const weightTrend = useMemo(() => {
    if (weightLog.length < 2) return null
    const sorted = [...weightLog].sort((a, b) => a.date.localeCompare(b.date))
    const latest = sorted[sorted.length - 1].kg
    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - weeks * 7)
    const cutoffStr = cutoffDate.toISOString().slice(0, 10)
    const windowEntries = sorted.filter(e => e.date >= cutoffStr)
    const oldest = windowEntries.length > 0 ? windowEntries[0].kg : sorted[0].kg
    const change = latest - oldest
    return { latest, change, entries: sorted.slice(-8) }
  }, [weightLog, weeks])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Weekly Analysis</h1>
        <div className="flex items-center gap-3">
          <select
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
            className="px-3 py-1.5 border border-border rounded-md bg-background text-sm"
          >
            <option value={1}>Last 1 week</option>
            <option value={2}>Last 2 weeks</option>
            <option value={4}>Last 4 weeks</option>
            <option value={8}>Last 8 weeks</option>
          </select>
          <div className="flex border border-border rounded-md overflow-hidden">
            <button
              onClick={() => setViewMode('raw')}
              className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 ${viewMode === 'raw' ? 'bg-primary text-primary-foreground' : 'bg-background text-muted-foreground'}`}
            >
              <TableIcon className="w-3.5 h-3.5" />
              Table
            </button>
            <button
              onClick={() => setViewMode('graph')}
              className={`px-2.5 py-1.5 text-xs font-medium flex items-center gap-1 ${viewMode === 'graph' ? 'bg-primary text-primary-foreground' : 'bg-background text-muted-foreground'}`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              Charts
            </button>
          </div>
          <a
            href="/fitness/api/export/xlsx"
            download="program_history.xlsx"
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:opacity-90 transition-opacity"
          >
            <Download className="w-4 h-4" />
            Export Excel
          </a>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center min-h-[20vh]">
          <div className="animate-pulse text-muted-foreground">Loading analysis...</div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Top summary cards - 4 columns */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">

            {/* Current Maxes */}
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Dumbbell className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Current Maxes</h3>
              </div>
              {data.current_maxes ? (
                <>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div>
                      <p className="text-xs text-muted-foreground">Squat</p>
                      <p className="text-lg font-bold">{data.current_maxes.squat?.toFixed(1) ?? '--'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Bench</p>
                      <p className="text-lg font-bold">{data.current_maxes.bench?.toFixed(1) ?? '--'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Deadlift</p>
                      <p className="text-lg font-bold">{data.current_maxes.deadlift?.toFixed(1) ?? '--'}</p>
                    </div>
                  </div>
                  {data.estimated_dots !== null && (
                    <p className="text-sm text-muted-foreground mt-1">
                      Est. DOTS: <span className="font-medium text-foreground">{data.estimated_dots.toFixed(2)}</span>
                    </p>
                  )}
                  {data.current_maxes.method && (
                    <p className="text-xs text-muted-foreground mt-1">
                      via {data.current_maxes.method === 'comp_results' ? 'competition' : data.current_maxes.method === 'session_estimated' ? 'session data' : data.current_maxes.method}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No max data available</p>
              )}
            </div>

            {/* Compliance */}
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Compliance</h3>
              </div>
              {data.compliance ? (
                <>
                  <p className={`text-3xl font-bold px-2 py-1 rounded inline-block ${complianceColor(data.compliance.pct)}`}>
                    {data.compliance.pct.toFixed(0)}%
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {data.compliance.completed}/{data.compliance.planned} sessions
                  </p>
                  <p className="text-xs text-muted-foreground">{data.compliance.phase} block</p>
                  {avgSessionsPerWeek !== null && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Avg {avgSessionsPerWeek} sessions/wk
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No compliance data</p>
              )}
            </div>

            {/* Fatigue Signal */}
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Fatigue Signal</h3>
              </div>
              <p className={`text-3xl font-bold px-2 py-1 rounded inline-block ${fatigueColor(data.fatigue_index)}`}>
                {data.fatigue_index !== null ? (data.fatigue_index * 100).toFixed(0) + '%' : 'N/A'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {fatigueLabel(data.fatigue_index)} risk
              </p>
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                Failed compounds: {((data.fatigue_components?.failed_compound_ratio ?? 0) * 100).toFixed(0)}%
                &middot; Fatigue spike: {((data.fatigue_components?.composite_spike ?? 0) * 100).toFixed(0)}%
                &middot; RPE stress: {((data.fatigue_components?.rpe_stress ?? 0) * 100).toFixed(0)}%
              </p>
            </div>

            {/* Readiness Score */}
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Readiness</h3>
              </div>
              {data.readiness_score ? (
                <>
                  <p className={`text-3xl font-bold px-2 py-1 rounded inline-block ${
                    data.readiness_score.zone === 'green' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : data.readiness_score.zone === 'yellow' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                    : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                  }`}>
                    {data.readiness_score.score.toFixed(0)}
                  </p>
                  <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                    Fatigue: {((data.readiness_score.components.fatigue_norm ?? 0) * 100).toFixed(0)}%
                    &middot; RPE drift: {((data.readiness_score.components.rpe_drift ?? 0) * 100).toFixed(0)}%
                    &middot; BW stability: {((data.readiness_score.components.bw_stability ?? 0) * 100).toFixed(0)}%
                    &middot; Miss rate: {((data.readiness_score.components.miss_rate ?? 0) * 100).toFixed(0)}%
                  </p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">N/A</p>
              )}
            </div>
          </div>

          {/* INOL Section */}
          {data.inol && data.inol.avg_inol && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">INOL (Window Average)</h3>
              <div className="grid grid-cols-3 gap-4 mb-3">
                {Object.entries(data.inol.avg_inol).map(([lift, val]) => (
                  <div key={lift} className="text-center p-3 bg-secondary/50 rounded">
                    <p className="text-xs text-muted-foreground capitalize">{lift}</p>
                    <p className={`text-2xl font-bold ${
                      val > 4.0 ? 'text-red-600' : val < 2.0 ? 'text-yellow-600' : 'text-green-600'
                    }`}>
                      {val.toFixed(2)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {val > 4.0 ? 'Overreaching' : val < 2.0 ? 'Low stimulus' : 'Productive'}
                    </p>
                  </div>
                ))}
              </div>
              {data.inol.flags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {data.inol.flags.map((flag) => (
                    <span key={flag} className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">
                      {flag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ACWR Section */}
          {data.acwr && !('status' in data.acwr) && (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium">ACWR (Acute:Chronic Workload Ratio)</h3>
                <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                  (data.acwr as any).composite_zone === 'optimal' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : (data.acwr as any).composite_zone === 'caution' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                  : (data.acwr as any).composite_zone === 'danger' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                  : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                }`}>
                  Composite: {(data.acwr as any).composite?.toFixed(2) ?? 'N/A'} ({(data.acwr as any).composite_zone})
                </span>
              </div>
              <div className="grid grid-cols-4 gap-4">
                {Object.entries((data.acwr as any).dimensions).map(([dim, info]: [string, any]) => {
                  const zoneColor = info.zone === 'optimal' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : info.zone === 'caution' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                    : info.zone === 'danger' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                  return (
                    <div key={dim} className={`text-center p-3 rounded ${zoneColor}`}>
                      <p className="text-xs capitalize">{dim}</p>
                      <p className="text-xl font-bold">{info.value?.toFixed(2) ?? '--'}</p>
                      <p className="text-xs capitalize">{info.zone}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
          {data.acwr && 'status' in data.acwr && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-2">ACWR (Acute:Chronic Workload Ratio)</h3>
              <p className="text-sm text-muted-foreground">
                {(data.acwr as any).reason ?? 'Not enough data yet. Keep logging sessions.'}
              </p>
            </div>
          )}

          {/* RI Distribution Section */}
          {data.ri_distribution && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Relative Intensity Distribution</h3>
              <div className="grid grid-cols-3 gap-4 mb-4">
                {(['heavy', 'moderate', 'light'] as const).map((bucket) => {
                  const info = data.ri_distribution!.overall[bucket]
                  const color = bucket === 'heavy' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    : bucket === 'moderate' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  return (
                    <div key={bucket} className={`text-center p-3 rounded ${color}`}>
                      <p className="text-xs capitalize">{bucket}</p>
                      <p className="text-2xl font-bold">{info.pct.toFixed(0)}%</p>
                      <p className="text-xs">{info.count} sets</p>
                    </div>
                  )
                })}
              </div>
              {Object.keys(data.ri_distribution.per_lift).length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-4">Lift</th>
                        <th className="text-right py-2 px-4">Heavy %</th>
                        <th className="text-right py-2 px-4">Moderate %</th>
                        <th className="text-right py-2 pl-4">Light %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(data.ri_distribution.per_lift).map(([lift, buckets]) => (
                        <tr key={lift} className="border-b border-border/50">
                          <td className="py-2 pr-4 font-medium capitalize">{lift}</td>
                          <td className="text-right py-2 px-4 text-red-600">{buckets.heavy.pct.toFixed(0)}%</td>
                          <td className="text-right py-2 px-4 text-green-600">{buckets.moderate.pct.toFixed(0)}%</td>
                          <td className="text-right py-2 pl-4 text-blue-600">{buckets.light.pct.toFixed(0)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Specificity Ratio Section */}
          {data.specificity_ratio && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Specificity Ratio</h3>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Narrow (SBD only)</p>
                  <div className="w-full bg-secondary rounded-full h-4 overflow-hidden">
                    <div
                      className="bg-primary h-4 rounded-full transition-all"
                      style={{ width: `${Math.min(data.specificity_ratio.narrow * 100, 100)}%` }}
                    />
                  </div>
                  <p className="text-sm font-medium mt-1">{(data.specificity_ratio.narrow * 100).toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Broad (SBD + secondary)</p>
                  <div className="w-full bg-secondary rounded-full h-4 overflow-hidden">
                    <div
                      className="bg-primary/70 h-4 rounded-full transition-all"
                      style={{ width: `${Math.min(data.specificity_ratio.broad * 100, 100)}%` }}
                    />
                  </div>
                  <p className="text-sm font-medium mt-1">{(data.specificity_ratio.broad * 100).toFixed(1)}%</p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-3">
                {data.specificity_ratio.sbd_sets} SBD sets / {data.specificity_ratio.total_sets} total sets
              </p>
            </div>
          )}

          {/* Fatigue Dimensions Section */}
          {data.fatigue_dimensions && Object.keys(data.fatigue_dimensions.weekly).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Fatigue Dimensions (Weekly)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4">Week</th>
                      <th className="text-right py-2 px-4">Axial</th>
                      <th className="text-right py-2 px-4">Neural</th>
                      <th className="text-right py-2 px-4">Peripheral</th>
                      <th className="text-right py-2 pl-4">Systemic</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.fatigue_dimensions.weekly)
                      .sort(([a], [b]) => Number(a) - Number(b))
                      .slice(-8)
                      .map(([week, dims]) => (
                        <tr key={week} className="border-b border-border/50">
                          <td className="py-2 pr-4 font-medium">W{week}</td>
                          <td className="text-right py-2 px-4">{dims.axial.toFixed(1)}</td>
                          <td className="text-right py-2 px-4">{dims.neural.toFixed(1)}</td>
                          <td className="text-right py-2 px-4">{dims.peripheral.toFixed(1)}</td>
                          <td className="text-right py-2 pl-4">{dims.systemic.toFixed(1)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              {(data.acwr && !('status' in data.acwr) && (data.acwr as any).dimensions) && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-3">
                  {Object.entries((data.acwr as any).dimensions).map(([dim, info]: [string, any]) =>
                    info.zone === 'caution' || info.zone === 'danger' ? (
                      <span key={dim} className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">
                        {dim.charAt(0).toUpperCase() + dim.slice(1)} overload (ACWR {info.value?.toFixed(2)})
                      </span>
                    ) : null
                  )}
                </div>
              )}
            </div>
          )}

          {/* Projection tiles (1-2 cards) */}
          {data.projections.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {data.projections.map((proj, i) => (
                <div key={i} className="bg-card border border-border rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    <h3 className="font-medium">{proj.comp_name || 'Projected Total'}</h3>
                  </div>
                  <p className="text-3xl font-bold">{proj.total.toFixed(1)} kg</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Confidence: {(proj.confidence * 100).toFixed(0)}%
                    {proj.weeks_to_comp !== undefined && ` (${proj.weeks_to_comp.toFixed(1)} wks out)`}
                  </p>
                  {proj.method && (
                    <p className="text-xs text-muted-foreground">
                      via {proj.method === 'session_estimated' ? 'session e1RM' : proj.method}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Projected Total</h3>
              </div>
              <p className="text-lg text-muted-foreground">{data.projection_reason || 'No competition date set'}</p>
            </div>
          )}

          {/* Weight Trend */}
          {weightTrend && (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Scale className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Body Weight Trend</h3>
              </div>
              <div className="flex items-baseline gap-4">
                <p className="text-2xl font-bold">{weightTrend.latest.toFixed(1)} kg</p>
                <p className={`text-sm font-medium ${weightTrend.change >= 0 ? 'text-yellow-600' : 'text-green-600'}`}>
                  {weightTrend.change >= 0 ? '+' : ''}{weightTrend.change.toFixed(1)} kg over {weeks} wk{weeks > 1 ? 's' : ''}
                </p>
              </div>
              <div className="mt-3 grid grid-cols-4 md:grid-cols-8 gap-2">
                {weightTrend.entries.map(e => (
                  <div key={e.date} className="text-center">
                    <p className="text-xs text-muted-foreground">{e.date.slice(5)}</p>
                    <p className="text-sm font-medium">{e.kg.toFixed(1)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fix 3: Nutrition Trend with +/- per week deltas */}
          {nutritionTrend && (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Utensils className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Nutrition Trend</h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {nutritionTrend.avgCalories !== null && (
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Avg Daily Calories</p>
                    <p className="text-lg font-bold">{nutritionTrend.avgCalories.toLocaleString()}</p>
                    {nutritionTrend.caloriesChangePerWeek !== null && (
                      <p className={`text-xs font-medium ${nutritionTrend.caloriesChangePerWeek >= 0 ? 'text-yellow-600' : 'text-green-600'}`}>
                        {nutritionTrend.caloriesChangePerWeek >= 0 ? '+' : ''}{nutritionTrend.caloriesChangePerWeek}/wk
                      </p>
                    )}
                  </div>
                )}
                {nutritionTrend.avgWater !== null && (
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Avg Water</p>
                    <p className="text-lg font-bold">{nutritionTrend.avgWater} {nutritionTrend.waterUnit === 'litres' ? 'L' : 'cups'}/day</p>
                    {nutritionTrend.waterChangePerWeek !== null && (
                      <p className={`text-xs font-medium ${nutritionTrend.waterChangePerWeek >= 0 ? 'text-blue-600' : 'text-orange-600'}`}>
                        {nutritionTrend.waterChangePerWeek >= 0 ? '+' : ''}{nutritionTrend.waterChangePerWeek} {nutritionTrend.waterUnit === 'litres' ? 'L' : 'cups'}/wk
                      </p>
                    )}
                  </div>
                )}
                {nutritionTrend.consistencyPct !== null && (
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Consistency</p>
                    <p className={`text-lg font-bold ${nutritionTrend.consistencyPct >= 80 ? 'text-green-600' : nutritionTrend.consistencyPct >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                      {nutritionTrend.consistencyPct}%
                    </p>
                  </div>
                )}
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">Entries</p>
                  <p className="text-lg font-bold">{nutritionTrend.entries}</p>
                </div>
              </div>
            </div>
          )}

          {/* Competitions */}
          {competitions.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Trophy className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Competitions</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4">Name</th>
                      <th className="text-left py-2 px-4">Date</th>
                      <th className="text-left py-2 px-4">Status</th>
                      <th className="text-right py-2 px-4">Squat</th>
                      <th className="text-right py-2 px-4">Bench</th>
                      <th className="text-right py-2 px-4">Deadlift</th>
                      <th className="text-right py-2 pl-4">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {competitions.map((c) => (
                      <tr key={c.date + c.name} className="border-b border-border/50">
                        <td className="py-2 pr-4 font-medium">{c.name}</td>
                        <td className="py-2 px-4 text-muted-foreground">{c.date}</td>
                        <td className="py-2 px-4">{compStatusBadge(c.status)}</td>
                        {c.results ? (
                          <>
                            <td className="text-right py-2 px-4">{c.results.squat_kg.toFixed(1)}</td>
                            <td className="text-right py-2 px-4">{c.results.bench_kg.toFixed(1)}</td>
                            <td className="text-right py-2 px-4">{c.results.deadlift_kg.toFixed(1)}</td>
                            <td className="text-right py-2 pl-4 font-bold">{c.results.total_kg.toFixed(1)}</td>
                          </>
                        ) : (
                          <td className="text-right py-2 pl-4 text-muted-foreground" colSpan={4}>--</td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Per-lift breakdown */}
          {Object.keys(data.lifts).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Per-Lift Breakdown</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4">Exercise</th>
                      <th className="text-right py-2 px-4">Freq</th>
                      <th className="text-right py-2 px-4">Sets</th>
                      <th className="text-right py-2 px-4">Progression</th>
                      <th className="text-right py-2 px-4">R&sup2;</th>
                      <th className="text-right py-2 px-4">Volume %</th>
                      <th className="text-right py-2 px-4">Intensity %</th>
                      <th className="text-right py-2 px-4">Failed</th>
                      <th className="text-right py-2 pl-4">RPE Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.lifts).map(([name, lift]) => {
                      const liftKey = name.toLowerCase().replace(' press', '')
                      const details = perLiftDetails[liftKey]
                      const isExpanded = expandedLifts.has(name)
                      return (
                        <Fragment key={name}>
                          <tr className="border-b border-border/50">
                            <td className="py-2 pr-4 font-medium capitalize">
                              <div className="flex items-center gap-2">
                                {name}
                                {details && details.accessories.length > 0 && (
                                  <button
                                    onClick={() => {
                                      setExpandedLifts(prev => {
                                        const next = new Set(prev)
                                        if (next.has(name)) next.delete(name)
                                        else next.add(name)
                                        return next
                                      })
                                    }}
                                    className="text-xs text-muted-foreground hover:text-foreground"
                                  >
                                    {isExpanded ? '\u25BC' : '\u25B6'} {details.accessories.length} acc
                                  </button>
                                )}
                              </div>
                            </td>
                            <td className="text-right py-2 px-4">
                              {details ? <span>{details.frequency}/wk</span> : <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="text-right py-2 px-4">
                              {details ? <span>{details.raw_sets}</span> : <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="text-right py-2 px-4">
                              {lift.progression_rate_kg_per_week !== undefined && lift.progression_rate_kg_per_week !== null
                                ? <span className={lift.progression_rate_kg_per_week >= 0 ? 'text-green-600' : 'text-red-600'}>
                                    {lift.progression_rate_kg_per_week >= 0 ? '+' : ''}{lift.progression_rate_kg_per_week.toFixed(1)} kg/wk
                                  </span>
                                : <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="text-right py-2 px-4">
                              {lift.r2 !== undefined && lift.r2 !== null
                                ? <span className="text-muted-foreground">{(lift.r2 * 100).toFixed(0)}%</span>
                                : <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="text-right py-2 px-4">
                              {lift.volume_change_pct !== undefined
                                ? <span className={lift.volume_change_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                                    {lift.volume_change_pct >= 0 ? '+' : ''}{lift.volume_change_pct.toFixed(0)}%
                                  </span>
                                : <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="text-right py-2 px-4">
                              {lift.intensity_change_pct !== undefined
                                ? <span className={lift.intensity_change_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                                    {lift.intensity_change_pct >= 0 ? '+' : ''}{lift.intensity_change_pct.toFixed(0)}%
                                  </span>
                                : <span className="text-muted-foreground">--</span>}
                            </td>
                            <td className="text-right py-2 px-4">
                              {lift.failed_sets !== undefined && lift.failed_sets > 0
                                ? <span className="text-red-600 font-medium">{lift.failed_sets}</span>
                                : <span className="text-muted-foreground">0</span>}
                            </td>
                            <td className="text-right py-2 pl-4">
                              {rpeTrendIcon(lift.rpe_trend) || <span className="text-muted-foreground">--</span>}
                            </td>
                          </tr>
                          {isExpanded && details && details.accessories.length > 0 && (
                            <tr className="border-b border-border/30 bg-secondary/20">
                              <td colSpan={9} className="py-2 px-4">
                                <div className="ml-4">
                                  <p className="text-xs text-muted-foreground mb-1">Accessory / Secondary Work</p>
                                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                                    {details.accessories.map(a => (
                                      <div key={a.name} className="text-xs p-1.5 bg-background rounded">
                                        <span className="font-medium">{a.name}</span>
                                        <span className="text-muted-foreground ml-2">{a.sets} sets</span>
                                        <span className="text-muted-foreground ml-2">{Math.round(a.volume).toLocaleString()} kg</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Exercise Stats — Fix 5: increased chart heights */}
          {data.exercise_stats && Object.keys(data.exercise_stats).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Exercise Volume</h3>
              {viewMode === 'raw' ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-4">Exercise</th>
                        <th className="text-right py-2 px-4">Total Sets</th>
                        <th className="text-right py-2 px-4">Volume (kg)</th>
                        <th className="text-right py-2 pl-4">Max (kg)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(data.exercise_stats)
                        .sort((a, b) => b[1].total_volume - a[1].total_volume)
                        .map(([name, s]) => (
                          <tr key={name} className="border-b border-border/50">
                            <td className="py-2 pr-4 font-medium">{name}</td>
                            <td className="text-right py-2 px-4">{s.total_sets}</td>
                            <td className="text-right py-2 px-4">{s.total_volume.toLocaleString()}</td>
                            <td className="text-right py-2 pl-4">{s.max_kg.toFixed(1)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Sets pie */}
                  <div>
                    <p className="text-xs text-muted-foreground text-center mb-2">Sets Distribution</p>
                    <ResponsiveContainer width="100%" height={350}>
                      <PieChart>
                        <Pie
                          data={Object.entries(data.exercise_stats)
                            .sort((a, b) => b[1].total_sets - a[1].total_sets)
                            .slice(0, 10)
                            .map(([name, s], i) => ({ name, value: s.total_sets, fill: CHART_COLORS[i % CHART_COLORS.length] }))}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={80}
                          label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                        >
                          {Object.entries(data.exercise_stats)
                            .sort((a, b) => b[1].total_sets - a[1].total_sets)
                            .slice(0, 10)
                            .map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Volume pie */}
                  <div>
                    <p className="text-xs text-muted-foreground text-center mb-2">Volume Distribution</p>
                    <ResponsiveContainer width="100%" height={350}>
                      <PieChart>
                        <Pie
                          data={Object.entries(data.exercise_stats)
                            .sort((a, b) => b[1].total_volume - a[1].total_volume)
                            .slice(0, 10)
                            .map(([name, s], i) => ({ name, value: s.total_volume, fill: CHART_COLORS[i % CHART_COLORS.length] }))}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={80}
                          label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                        >
                          {Object.entries(data.exercise_stats)
                            .sort((a, b) => b[1].total_volume - a[1].total_volume)
                            .slice(0, 10)
                            .map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Max bar — Fix 5: height 350, YAxis width 130, fontSize 12 */}
                  <div>
                    <p className="text-xs text-muted-foreground text-center mb-2">Max Weight (kg)</p>
                    <ResponsiveContainer width="100%" height={350}>
                      <BarChart
                        data={Object.entries(data.exercise_stats)
                          .sort((a, b) => b[1].max_kg - a[1].max_kg)
                          .slice(0, 10)
                          .map(([name, s], i) => ({ name, max_kg: s.max_kg, fill: CHART_COLORS[i % CHART_COLORS.length] }))}
                        layout="vertical"
                      >
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" />
                        <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12 }} />
                        <Tooltip />
                        <Bar dataKey="max_kg" radius={[0, 4, 4, 0]}>
                          {Object.entries(data.exercise_stats)
                            .sort((a, b) => b[1].max_kg - a[1].max_kg)
                            .slice(0, 10)
                            .map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Muscle Group Sets */}
          {Object.keys(muscleGroupSets).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Sets by Muscle Group</h3>
              {viewMode === 'raw' ? (
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  {Object.entries(muscleGroupSets)
                    .sort((a, b) => b[1] - a[1])
                    .map(([muscle, sets]) => (
                      <div key={muscle} className="text-center p-2 bg-secondary/50 rounded">
                        <p className="text-xs text-muted-foreground capitalize">{muscle.replace(/_/g, ' ')}</p>
                        <p className="text-lg font-bold">{Math.round(sets)}</p>
                      </div>
                    ))}
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={Object.entries(muscleGroupSets)
                        .sort((a, b) => b[1] - a[1])
                        .map(([name, value], i) => ({ name: name.replace(/_/g, ' '), value, fill: CHART_COLORS[i % CHART_COLORS.length] }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {Object.entries(muscleGroupSets)
                        .sort((a, b) => b[1] - a[1])
                        .map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

          {/* Volume by Muscle Group */}
          {Object.keys(muscleGroupVolume).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Volume by Muscle Group</h3>
              {viewMode === 'raw' ? (
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  {Object.entries(muscleGroupVolume)
                    .sort((a, b) => b[1] - a[1])
                    .map(([muscle, vol]) => (
                      <div key={muscle} className="text-center p-2 bg-secondary/50 rounded">
                        <p className="text-xs text-muted-foreground capitalize">{muscle.replace(/_/g, ' ')}</p>
                        <p className="text-lg font-bold">{Math.round(vol).toLocaleString()} kg</p>
                      </div>
                    ))}
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={Object.entries(muscleGroupVolume)
                        .sort((a, b) => b[1] - a[1])
                        .map(([name, value], i) => ({ name: name.replace(/_/g, ' '), value, fill: CHART_COLORS[i % CHART_COLORS.length] }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {Object.entries(muscleGroupVolume)
                        .sort((a, b) => b[1] - a[1])
                        .map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

          {/* Fix 4: Avg Weekly by Muscle Group — separate charts */}
          {Object.keys(muscleGroupAvgWeekly.sets).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Avg Weekly by Muscle Group</h3>
              {viewMode === 'raw' ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-4">Muscle Group</th>
                        <th className="text-right py-2 px-4">Avg Sets/wk</th>
                        <th className="text-right py-2 pl-4">Avg Vol/wk (kg)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(muscleGroupAvgWeekly.sets)
                        .sort((a, b) => (muscleGroupAvgWeekly.volume[b[0]] || 0) - (muscleGroupAvgWeekly.volume[a[0]] || 0))
                        .map(([muscle, sets]) => (
                          <tr key={muscle} className="border-b border-border/50">
                            <td className="py-2 pr-4 font-medium capitalize">{muscle.replace(/_/g, ' ')}</td>
                            <td className="text-right py-2 px-4">{sets}</td>
                            <td className="text-right py-2 pl-4">{(muscleGroupAvgWeekly.volume[muscle] || 0).toLocaleString()}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground text-center mb-2">Avg Sets/wk</p>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart
                        data={Object.entries(muscleGroupAvgWeekly.sets)
                          .sort((a, b) => b[1] - a[1])
                          .map(([name, value]) => ({ name: name.replace(/_/g, ' '), 'Avg Sets/wk': value }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="Avg Sets/wk" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground text-center mb-2">Avg Vol/wk (kg)</p>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart
                        data={Object.entries(muscleGroupAvgWeekly.volume)
                          .sort((a, b) => b[1] - a[1])
                          .map(([name, value]) => ({ name: name.replace(/_/g, ' '), 'Avg Vol/wk': value }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="Avg Vol/wk" fill="#22c55e" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Attempt Selector Settings */}
          {data.attempt_selection && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-1">Competition Attempt Percentages</h3>
              <p className="text-xs text-muted-foreground mb-3">Based on projected competition maxes. Enter as decimal (e.g. 0.90 for 90%).</p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs text-muted-foreground">Opener</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={attemptPct.opener}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value)
                      if (!isNaN(v) && v >= 0.70 && v <= 1.10) setAttemptPct(p => ({ ...p, opener: v }))
                      else if (e.target.value === '' || e.target.value.endsWith('.')) setAttemptPct(p => ({ ...p, opener: parseFloat(e.target.value.replace(/[^0-9.]/g, '')) || p.opener }))
                    }}
                    onBlur={(e) => {
                      const v = parseFloat(e.target.value)
                      const valid = !isNaN(v) && v >= 0.70 && v <= 1.10
                      if (!valid) setAttemptPct(p => ({ ...p, opener: 0.90 }))
                      setSavingAttempt(true)
                      updateMetaField(version, 'attempt_pct', attemptPct).finally(() => setSavingAttempt(false))
                    }}
                    className="w-full mt-1 px-2 py-1 border border-border rounded bg-background text-sm"
                  />
                  <p className="text-xs text-muted-foreground mt-1">Should feel easy under worst conditions</p>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Second</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={attemptPct.second}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value)
                      if (!isNaN(v) && v >= 0.70 && v <= 1.10) setAttemptPct(p => ({ ...p, second: v }))
                    }}
                    onBlur={(e) => {
                      const v = parseFloat(e.target.value)
                      const valid = !isNaN(v) && v >= 0.70 && v <= 1.10
                      if (!valid) setAttemptPct(p => ({ ...p, second: 0.955 }))
                      setSavingAttempt(true)
                      updateMetaField(version, 'attempt_pct', attemptPct).finally(() => setSavingAttempt(false))
                    }}
                    className="w-full mt-1 px-2 py-1 border border-border rounded bg-background text-sm"
                  />
                  <p className="text-xs text-muted-foreground mt-1">A confident single, builds momentum</p>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Third</label>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={attemptPct.third}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value)
                      if (!isNaN(v) && v >= 0.70 && v <= 1.10) setAttemptPct(p => ({ ...p, third: v }))
                    }}
                    onBlur={(e) => {
                      const v = parseFloat(e.target.value)
                      const valid = !isNaN(v) && v >= 0.70 && v <= 1.10
                      if (!valid) setAttemptPct(p => ({ ...p, third: 1.00 }))
                      setSavingAttempt(true)
                      updateMetaField(version, 'attempt_pct', attemptPct).finally(() => setSavingAttempt(false))
                    }}
                    className="w-full mt-1 px-2 py-1 border border-border rounded bg-background text-sm"
                  />
                  <p className="text-xs text-muted-foreground mt-1">Your projected max &mdash; go for it</p>
                </div>
              </div>
              {savingAttempt && <p className="text-xs text-muted-foreground mt-2">Saving...</p>}
              {/* Display computed attempts */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {Object.entries(data.attempt_selection)
                  .filter(([k]) => k !== 'total' && k !== 'attempt_pct_used')
                  .map(([lift, attempts]) => (
                    <div key={lift} className="text-center">
                      <div className="font-medium capitalize">{lift}</div>
                      <div className="text-xs text-muted-foreground">
                        {(attempts as { opener: number; second: number; third: number }).opener} / {(attempts as { opener: number; second: number; third: number }).second} / {(attempts as { opener: number; second: number; third: number }).third} kg
                      </div>
                    </div>
                  ))}
                {data.attempt_selection.total !== undefined && (
                  <div className="text-center col-span-3 mt-2 pt-2 border-t border-border">
                    <span className="font-medium">Projected total: {data.attempt_selection.total} kg</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Formula Reference */}
          <div className="mt-8">
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-gray-400 hover:text-gray-200">
                How These Numbers Are Calculated
              </summary>
              <div className="mt-4 space-y-2">
                {FORMULA_DESCRIPTIONS.map(formula => (
                  <details key={formula.id} className="border border-gray-700 rounded-lg">
                    <summary className="px-4 py-2 cursor-pointer text-sm font-medium">
                      {formula.title}
                    </summary>
                    <div className="px-4 py-3 space-y-2 text-sm text-gray-300">
                      <p>{formula.summary}</p>
                      <pre className="bg-gray-800 rounded p-3 font-mono text-xs overflow-x-auto">
                        {formula.formula}
                      </pre>
                      {formula.variables && (
                        <div className="grid grid-cols-2 gap-1 text-xs">
                          {formula.variables.map(v => (
                            <div key={v.name}><code>{v.name}</code>: {v.description}</div>
                          ))}
                        </div>
                      )}
                      {formula.thresholds && (
                        <table className="w-full text-xs mt-2">
                          <thead><tr><th className="text-left">Condition</th><th className="text-left">Value</th><th className="text-left">Flag</th></tr></thead>
                          <tbody>
                            {formula.thresholds.map(t => (
                              <tr key={t.label}><td className="py-0.5">{t.label}</td><td className="py-0.5">{t.value}</td><td className="py-0.5">{t.flag || '\u2014'}</td></tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            </details>
          </div>

          {/* Flags */}
          {data.flags.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-5 h-5 text-yellow-500" />
                <h3 className="font-medium">Flags</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.flags.map((flag) => (
                  <span
                    key={flag}
                    className="px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                  >
                    {flag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Footer info */}
          <p className="text-xs text-muted-foreground">
            Week {data.week} ({data.block}) &middot; {data.sessions_analyzed} sessions analyzed
          </p>
        </>
      )}

      {!data && !loading && !error && (
        <div className="flex items-center justify-center min-h-[20vh]">
          <p className="text-muted-foreground">No analysis data available for the selected period.</p>
        </div>
      )}
    </div>
  )
}
