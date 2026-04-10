import { useState, useEffect, useMemo, Fragment } from 'react'
import { Activity, Download, AlertTriangle, CheckCircle, TrendingUp, Dumbbell, Trophy, Scale, Table as TableIcon, BarChart3, Utensils } from 'lucide-react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { fetchWeeklyAnalysis, type WeeklyAnalysis } from '@/api/analytics'
import { useProgramStore } from '@/store/programStore'
import { fetchWeightLog, fetchGlossary } from '@/api/client'
import { normalizeExerciseName } from '@/utils/volume'
import type { WeightEntry, GlossaryExercise, Competition, FatigueCategory, ExerciseCategory } from '@powerlifting/types'

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

const FATIGUE_LABELS: Record<FatigueCategory, string> = {
  primary_axial: 'Primary Axial',
  primary_upper: 'Primary Upper',
  secondary: 'Secondary',
  accessory: 'Accessory',
}

const FATIGUE_ORDER: FatigueCategory[] = ['primary_axial', 'primary_upper', 'secondary', 'accessory']

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

  // Muscle group sets aggregation
  const muscleGroupSets = useMemo(() => {
    if (!glossary.length || !program?.sessions) return {}
    const lookup = new Map<string, { primary: string[]; secondary: string[] }>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), {
        primary: ex.primary_muscles,
        secondary: ex.secondary_muscles,
      })
    }

    const filtered = program.sessions.filter(s => (s.block ?? 'current') === 'current' && s.completed)
    const mgSets: Record<string, number> = {}
    for (const s of filtered) {
      for (const ex of s.exercises || []) {
        const muscles = lookup.get(normalizeExerciseName(ex.name))
        if (!muscles) continue
        const sets = ex.sets || 0
        for (const m of muscles.primary) mgSets[m] = (mgSets[m] || 0) + sets
        for (const m of muscles.secondary) mgSets[m] = (mgSets[m] || 0) + sets * 0.5
      }
    }
    return mgSets
  }, [glossary, program?.sessions])

  // Fatigue category sets aggregation
  const fatigueCategorySets = useMemo(() => {
    if (!glossary.length || !program?.sessions) return {}
    const lookup = new Map<string, FatigueCategory>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), ex.fatigue_category)
    }

    const filtered = program.sessions.filter(s => (s.block ?? 'current') === 'current' && s.completed)
    const fcSets: Record<string, number> = {}
    for (const s of filtered) {
      for (const ex of s.exercises || []) {
        const fc = lookup.get(normalizeExerciseName(ex.name))
        if (!fc) continue
        fcSets[fc] = (fcSets[fc] || 0) + (ex.sets || 0)
      }
    }
    return fcSets
  }, [glossary, program?.sessions])

  // Muscle group volume aggregation
  const muscleGroupVolume = useMemo(() => {
    if (!glossary.length || !program?.sessions) return {}
    const lookup = new Map<string, { primary: string[]; secondary: string[] }>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), {
        primary: ex.primary_muscles,
        secondary: ex.secondary_muscles,
      })
    }

    const filtered = program.sessions.filter(s => (s.block ?? 'current') === 'current' && s.completed)
    const mgVol: Record<string, number> = {}
    for (const s of filtered) {
      for (const ex of s.exercises || []) {
        const muscles = lookup.get(normalizeExerciseName(ex.name))
        if (!muscles) continue
        const vol = (ex.sets || 0) * (ex.reps || 0) * (ex.kg || 0)
        for (const m of muscles.primary) mgVol[m] = (mgVol[m] || 0) + vol
        for (const m of muscles.secondary) mgVol[m] = (mgVol[m] || 0) + vol * 0.5
      }
    }
    return mgVol
  }, [glossary, program?.sessions])

  // Fatigue category volume aggregation
  const fatigueCategoryVolume = useMemo(() => {
    if (!glossary.length || !program?.sessions) return {}
    const lookup = new Map<string, FatigueCategory>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), ex.fatigue_category)
    }

    const filtered = program.sessions.filter(s => (s.block ?? 'current') === 'current' && s.completed)
    const fcVol: Record<string, number> = {}
    for (const s of filtered) {
      for (const ex of s.exercises || []) {
        const fc = lookup.get(normalizeExerciseName(ex.name))
        if (!fc) continue
        const vol = (ex.sets || 0) * (ex.reps || 0) * (ex.kg || 0)
        fcVol[fc] = (fcVol[fc] || 0) + vol
      }
    }
    return fcVol
  }, [glossary, program?.sessions])

  // Avg per week: muscle group
  const muscleGroupAvgWeekly = useMemo(() => {
    if (!glossary.length || !program?.sessions) return { sets: {}, volume: {} }
    const lookup = new Map<string, { primary: string[]; secondary: string[] }>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), {
        primary: ex.primary_muscles,
        secondary: ex.secondary_muscles,
      })
    }

    const filtered = program.sessions.filter(s => (s.block ?? 'current') === 'current' && s.completed)
    const numWeeks = new Set(filtered.map(s => s.week_number)).size || 1
    const mgSets: Record<string, number> = {}
    const mgVol: Record<string, number> = {}
    for (const s of filtered) {
      for (const ex of s.exercises || []) {
        const muscles = lookup.get(normalizeExerciseName(ex.name))
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
  }, [glossary, program?.sessions])

  // Avg per week: fatigue category
  const fatigueCategoryAvgWeekly = useMemo(() => {
    if (!glossary.length || !program?.sessions) return { sets: {}, volume: {} }
    const lookup = new Map<string, FatigueCategory>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), ex.fatigue_category)
    }

    const filtered = program.sessions.filter(s => (s.block ?? 'current') === 'current' && s.completed)
    const numWeeks = new Set(filtered.map(s => s.week_number)).size || 1
    const fcSets: Record<string, number> = {}
    const fcVol: Record<string, number> = {}
    for (const s of filtered) {
      for (const ex of s.exercises || []) {
        const fc = lookup.get(normalizeExerciseName(ex.name))
        if (!fc) continue
        const sets = ex.sets || 0
        const vol = sets * (ex.reps || 0) * (ex.kg || 0)
        fcSets[fc] = (fcSets[fc] || 0) + sets
        fcVol[fc] = (fcVol[fc] || 0) + vol
      }
    }
    const avgSets: Record<string, number> = {}
    const avgVol: Record<string, number> = {}
    for (const fc of Object.keys(fcSets)) {
      avgSets[fc] = Math.round((fcSets[fc] / numWeeks) * 10) / 10
      avgVol[fc] = Math.round(fcVol[fc] / numWeeks)
    }
    return { sets: avgSets, volume: avgVol }
  }, [glossary, program?.sessions])

  // Per-lift details: frequency, raw sets, accessory work
  const perLiftDetails = useMemo(() => {
    if (!glossary.length || !program?.sessions) return {}
    const filtered = program.sessions.filter(s => (s.block ?? 'current') === 'current' && s.completed)
    const numWeeks = new Set(filtered.map(s => s.week_number)).size || 1

    const glossaryLookup = new Map<string, { category: ExerciseCategory; fatigue_category: FatigueCategory }>()
    for (const ex of glossary) {
      glossaryLookup.set(normalizeExerciseName(ex.name), { category: ex.category, fatigue_category: ex.fatigue_category })
    }

    const result: Record<string, { frequency: number; raw_sets: number; accessories: { name: string; sets: number; volume: number }[] }> = {}

    for (const [liftName, category] of [['squat', 'squat'], ['bench', 'bench'], ['deadlift', 'deadlift']] as const) {
      let liftSessions = 0
      let rawSets = 0
      const accessoryMap: Record<string, { sets: number; volume: number }> = {}

      for (const s of filtered) {
        let hasLift = false
        for (const ex of s.exercises || []) {
          const exLower = ex.name.toLowerCase().trim()
          const info = glossaryLookup.get(normalizeExerciseName(ex.name))
          if (exLower === liftName || (liftName === 'bench' && exLower === 'bench press')) {
            hasLift = true
            rawSets += ex.sets || 0
          }
          if (info && info.category === category && (info.fatigue_category === 'secondary' || info.fatigue_category === 'accessory')) {
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
  }, [glossary, program?.sessions])

  // Avg sessions per week
  const avgSessionsPerWeek = data ? Math.round((data.sessions_analyzed / weeks) * 10) / 10 : null

  // Nutrition trend
  const nutritionTrend = useMemo(() => {
    if (!program?.diet_notes?.length) return null
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - weeks * 7)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    const inWindow = program.diet_notes.filter(n => n.date >= cutoffStr)
    if (!inWindow.length) return null
    const withCalories = inWindow.filter(n => n.avg_daily_calories != null)
    const withWater = inWindow.filter(n => n.water_intake != null)
    const consistent = inWindow.filter(n => n.consistent).length
    return {
      avgCalories: withCalories.length ? Math.round(withCalories.reduce((s, n) => s + (n.avg_daily_calories || 0), 0) / withCalories.length) : null,
      avgWater: withWater.length ? Math.round(withWater.reduce((s, n) => s + (n.water_intake || 0), 0) / withWater.length * 10) / 10 : null,
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

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
                &middot; Load spike: {((data.fatigue_components?.fatigue_load_spike ?? 0) * 100).toFixed(0)}%
                &middot; Skip rate: {((data.fatigue_components?.skip_rate ?? 0) * 100).toFixed(0)}%
              </p>
            </div>
          </div>

          {/* Projection tiles (1-2 cards) */}
          {data.projections.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

          {/* Nutrition Trend */}
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
                  </div>
                )}
                {nutritionTrend.avgWater !== null && (
                  <div className="text-center">
                    <p className="text-xs text-muted-foreground">Avg Water</p>
                    <p className="text-lg font-bold">{nutritionTrend.avgWater} {nutritionTrend.waterUnit === 'litres' ? 'L' : 'cups'}/day</p>
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

          {/* Exercise Stats */}
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
                    <ResponsiveContainer width="100%" height={250}>
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
                    <ResponsiveContainer width="100%" height={250}>
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
                  {/* Max bar */}
                  <div>
                    <p className="text-xs text-muted-foreground text-center mb-2">Max Weight (kg)</p>
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart
                        data={Object.entries(data.exercise_stats)
                          .sort((a, b) => b[1].max_kg - a[1].max_kg)
                          .slice(0, 10)
                          .map(([name, s], i) => ({ name, max_kg: s.max_kg, fill: CHART_COLORS[i % CHART_COLORS.length] }))}
                        layout="vertical"
                      >
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" />
                        <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
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

          {/* Fatigue Category Sets */}
          {Object.keys(fatigueCategorySets).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Sets by Fatigue Category</h3>
              {viewMode === 'raw' ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {FATIGUE_ORDER.map(fc => {
                    const sets = fatigueCategorySets[fc]
                    if (!sets) return null
                    return (
                      <div key={fc} className="text-center p-3 bg-secondary/50 rounded">
                        <p className="text-xs text-muted-foreground">{FATIGUE_LABELS[fc]}</p>
                        <p className="text-lg font-bold">{sets}</p>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={FATIGUE_ORDER
                        .filter(fc => fatigueCategorySets[fc])
                        .map((fc, i) => ({ name: FATIGUE_LABELS[fc], value: fatigueCategorySets[fc] }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {FATIGUE_ORDER.filter(fc => fatigueCategorySets[fc]).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
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

          {/* Volume by Fatigue Category */}
          {Object.keys(fatigueCategoryVolume).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Volume by Fatigue Category</h3>
              {viewMode === 'raw' ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {FATIGUE_ORDER.map(fc => {
                    const vol = fatigueCategoryVolume[fc]
                    if (!vol) return null
                    return (
                      <div key={fc} className="text-center p-3 bg-secondary/50 rounded">
                        <p className="text-xs text-muted-foreground">{FATIGUE_LABELS[fc]}</p>
                        <p className="text-lg font-bold">{Math.round(vol).toLocaleString()} kg</p>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={FATIGUE_ORDER
                        .filter(fc => fatigueCategoryVolume[fc])
                        .map((fc, i) => ({ name: FATIGUE_LABELS[fc], value: fatigueCategoryVolume[fc] }))}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {FATIGUE_ORDER.filter(fc => fatigueCategoryVolume[fc]).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

          {/* Avg Weekly by Muscle Group */}
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
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart
                    data={Object.entries(muscleGroupAvgWeekly.sets)
                      .sort((a, b) => (muscleGroupAvgWeekly.volume[b[0]] || 0) - (muscleGroupAvgWeekly.volume[a[0]] || 0))
                      .map(([name]) => ({
                        name: name.replace(/_/g, ' '),
                        'Avg Sets/wk': muscleGroupAvgWeekly.sets[name],
                        'Avg Vol/wk': Math.round((muscleGroupAvgWeekly.volume[name] || 0) / 100),
                      }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="Avg Sets/wk" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Avg Vol/wk" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

          {/* Avg Weekly by Fatigue Category */}
          {Object.keys(fatigueCategoryAvgWeekly.sets).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Avg Weekly by Fatigue Category</h3>
              {viewMode === 'raw' ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-4">Category</th>
                        <th className="text-right py-2 px-4">Avg Sets/wk</th>
                        <th className="text-right py-2 pl-4">Avg Vol/wk (kg)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {FATIGUE_ORDER.map(fc => {
                        const sets = fatigueCategoryAvgWeekly.sets[fc]
                        const vol = fatigueCategoryAvgWeekly.volume[fc]
                        if (!sets && !vol) return null
                        return (
                          <tr key={fc} className="border-b border-border/50">
                            <td className="py-2 pr-4 font-medium">{FATIGUE_LABELS[fc]}</td>
                            <td className="text-right py-2 px-4">{sets || 0}</td>
                            <td className="text-right py-2 pl-4">{(vol || 0).toLocaleString()}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart
                    data={FATIGUE_ORDER
                      .filter(fc => fatigueCategoryAvgWeekly.sets[fc] || fatigueCategoryAvgWeekly.volume[fc])
                      .map(fc => ({
                        name: FATIGUE_LABELS[fc],
                        'Avg Sets/wk': fatigueCategoryAvgWeekly.sets[fc] || 0,
                        'Avg Vol/wk': Math.round((fatigueCategoryAvgWeekly.volume[fc] || 0) / 100),
                      }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="Avg Sets/wk" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Avg Vol/wk" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          )}

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
