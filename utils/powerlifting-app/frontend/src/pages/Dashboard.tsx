import { useState, useEffect } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { fetchWeightLog } from '@/api/client'
import { daysUntil, formatDateShort, sessionsThisCalendarWeek } from '@/utils/dates'
import { displayWeight, toDisplayUnit, fromDisplayUnit } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import { CalendarDays, Target, Scale, Trophy, TrendingUp, Edit2, Save, X, Plus, Trash2, Download, Dumbbell } from 'lucide-react'
import type { Phase, WeightEntry, LiftProfile } from '@powerlifting/types'

const LIFT_LABELS: Record<LiftProfile['lift'], string> = {
  squat: 'Squat',
  bench: 'Bench',
  deadlift: 'Deadlift',
}

const LIFT_STYLE_PLACEHOLDERS: Record<LiftProfile['lift'], string> = {
  squat: 'e.g. High bar, hip width stance, knees track over toes, upright torso. Belt squat occasionally for back relief.',
  bench: 'e.g. Close grip for ROM, moderate arch, explosive leg drive, bar slightly below nipples, let bar sink slightly before explode.',
  deadlift: 'e.g. Conventional, double overhand / mixed grip at heavy, slight wedge off floor, lockout hip drive.',
}

const STICKING_PLACEHOLDERS: Record<LiftProfile['lift'], string> = {
  squat: 'e.g. Out of the hole just below parallel, hamstring activation drops',
  bench: 'e.g. Off the chest – initial drive phase, first 2-3 inches',
  deadlift: 'e.g. Below the knee transitioning off the floor, hip-hinge not engaged early enough',
}

const DEFAULT_PROFILE = (lift: LiftProfile['lift']): LiftProfile => ({
  lift,
  style_notes: '',
  sticking_points: '',
  primary_muscle: '',
  volume_tolerance: 'moderate',
})

export default function Dashboard() {
  const { program, version, isLoading, updateMaxes, updateBodyWeight, updatePhases, updateLiftProfiles } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()

  const [editingMaxes, setEditingMaxes] = useState(false)
  const [editingWeight, setEditingWeight] = useState(false)
  const [editingPhases, setEditingPhases] = useState(false)
  const [editingLiftProfiles, setEditingLiftProfiles] = useState(false)
  const [localMaxes, setLocalMaxes] = useState({ squat: 0, bench: 0, deadlift: 0 })
  const [localWeight, setLocalWeight] = useState(0)
  const [localPhases, setLocalPhases] = useState<Phase[]>([])
  const [localLiftProfiles, setLocalLiftProfiles] = useState<LiftProfile[]>([])
  const [weightLog, setWeightLog] = useState<WeightEntry[]>([])

  useEffect(() => {
    if (version) {
      fetchWeightLog(version)
        .then(setWeightLog)
        .catch((e) => console.error('Failed to load weight log:', e))
    }
  }, [version])

  useEffect(() => {
    if (program?.lift_profiles) {
      setLocalLiftProfiles(program.lift_profiles)
    } else {
      // Initialize with defaults for all 3 lifts
      setLocalLiftProfiles([
        DEFAULT_PROFILE('squat'),
        DEFAULT_PROFILE('bench'),
        DEFAULT_PROFILE('deadlift'),
      ])
    }
  }, [program?.lift_profiles])

  if (isLoading || !program) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    )
  }

  const { meta, sessions, phases, competitions } = program
  const thisWeekSessions = sessionsThisCalendarWeek(sessions)
  const completedThisWeek = thisWeekSessions.filter((s) => s.completed).length

  const upcomingComps = competitions
    .filter((c) => c.status !== 'skipped' && new Date(c.date) >= new Date())
    .sort((a, b) => a.date.localeCompare(b.date))

  const latestWeightKg = weightLog.length > 0 ? weightLog[0].kg : meta.current_body_weight_kg

  const actualMaxes = { squat: 0, bench: 0, deadlift: 0 }
  for (const session of sessions) {
    if (!session.completed) continue
    if ((session.block || 'current') !== 'current') continue
    for (const exercise of session.exercises) {
      if (exercise.kg == null) continue
      const name = exercise.name.toLowerCase()
      if (name.includes('squat') && exercise.kg > actualMaxes.squat) actualMaxes.squat = exercise.kg
      if (name.includes('bench') && exercise.kg > actualMaxes.bench) actualMaxes.bench = exercise.kg
      if (name.includes('deadlift') && exercise.kg > actualMaxes.deadlift) actualMaxes.deadlift = exercise.kg
    }
  }

  const currentPhase = thisWeekSessions[0]?.phase

  const startEditingMaxes = () => {
    setLocalMaxes({ squat: meta.target_squat_kg, bench: meta.target_bench_kg, deadlift: meta.target_dl_kg })
    setEditingMaxes(true)
  }

  const saveMaxes = async () => {
    try {
      await updateMaxes({ squat_kg: localMaxes.squat, bench_kg: localMaxes.bench, deadlift_kg: localMaxes.deadlift })
      pushToast({ message: 'Target maxes updated', type: 'success' })
      setEditingMaxes(false)
    } catch (err) {
      pushToast({ message: 'Failed to update maxes', type: 'error' })
    }
  }

  const startEditingWeight = () => {
    setLocalWeight(latestWeightKg)
    setEditingWeight(true)
  }

  const saveWeight = async () => {
    try {
      await updateBodyWeight(localWeight)
      pushToast({ message: 'Body weight updated', type: 'success' })
      setEditingWeight(false)
    } catch (err) {
      pushToast({ message: 'Failed to update weight', type: 'error' })
    }
  }

  const startEditingPhases = () => {
    setLocalPhases([...phases])
    setEditingPhases(true)
  }

  const savePhases = async () => {
    try {
      await updatePhases(localPhases)
      pushToast({ message: 'Phases updated', type: 'success' })
      setEditingPhases(false)
    } catch (err) {
      pushToast({ message: 'Failed to update phases', type: 'error' })
    }
  }

  const updatePhase = (index: number, field: keyof Phase, value: string | number) => {
    setLocalPhases(prev => {
      const updated = [...prev]
      updated[index] = { ...updated[index], [field]: value }
      return updated
    })
  }

  const addPhase = () => {
    const lastPhase = localPhases[localPhases.length - 1]
    const newStart = lastPhase ? lastPhase.end_week + 1 : 1
    setLocalPhases(prev => [...prev, { name: 'New Phase', intent: '', start_week: newStart, end_week: newStart + 3 }])
  }

  const removePhase = (index: number) => setLocalPhases(prev => prev.filter((_, i) => i !== index))

  const startEditingLiftProfiles = () => {
    const existing = program?.lift_profiles || []
    const merged: LiftProfile[] = (['squat', 'bench', 'deadlift'] as const).map(lift =>
      existing.find(p => p.lift === lift) ?? DEFAULT_PROFILE(lift)
    )
    setLocalLiftProfiles(merged)
    setEditingLiftProfiles(true)
  }

  const saveLiftProfiles = async () => {
    try {
      await updateLiftProfiles(localLiftProfiles)
      pushToast({ message: 'Lift profiles saved', type: 'success' })
      setEditingLiftProfiles(false)
    } catch (err) {
      pushToast({ message: 'Failed to save lift profiles', type: 'error' })
    }
  }

  const updateLocalProfile = (lift: LiftProfile['lift'], updates: Partial<LiftProfile>) => {
    setLocalLiftProfiles(prev =>
      prev.map(p => p.lift === lift ? { ...p, ...updates } : p)
    )
  }

  const displayProfiles = (program?.lift_profiles?.length
    ? program.lift_profiles
    : (['squat', 'bench', 'deadlift'] as const).map(DEFAULT_PROFILE)
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <a
          href="/api/export/xlsx"
          download="program_history.xlsx"
          className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:opacity-90 transition-opacity"
        >
          <Download className="w-4 h-4" />
          Export Excel
        </a>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Upcoming Competitions */}
        {upcomingComps.length > 0 && (
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Trophy className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Upcoming Competitions</h3>
            </div>
            <div className="space-y-2">
              {upcomingComps.map((comp) => (
                <div key={comp.date} className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`shrink-0 text-xs px-1.5 py-0.5 rounded-full ${
                      comp.status === 'confirmed'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                    }`}>
                      {comp.status}
                    </span>
                    <span className="text-sm truncate">{comp.name}</span>
                  </div>
                  <span className="text-sm font-medium shrink-0 ml-2">{daysUntil(comp.date)}d</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Target Maxes */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Target Maxes</h3>
            </div>
            {editingMaxes ? (
              <div className="flex gap-1">
                <button onClick={saveMaxes} className="p-1 hover:bg-accent rounded text-primary"><Save className="w-4 h-4" /></button>
                <button onClick={() => setEditingMaxes(false)} className="p-1 hover:bg-accent rounded"><X className="w-4 h-4" /></button>
              </div>
            ) : (
              <button onClick={startEditingMaxes} className="p-1 hover:bg-accent rounded"><Edit2 className="w-4 h-4 text-muted-foreground" /></button>
            )}
          </div>
          {editingMaxes ? (
            <div className="space-y-2">
              {(['squat', 'bench', 'deadlift'] as const).map((lift) => (
                <div key={lift} className="flex items-center gap-2">
                  <span className="w-16 text-sm capitalize">{lift}</span>
                  <input
                    type="number"
                    value={toDisplayUnit(localMaxes[lift], unit)}
                    onChange={(e) => setLocalMaxes(prev => ({ ...prev, [lift]: fromDisplayUnit(Number(e.target.value), unit) }))}
                    className="flex-1 px-2 py-1 border border-border rounded bg-background text-sm"
                  />
                  <span className="text-xs text-muted-foreground">{unit}</span>
                </div>
              ))}
              <div className="flex justify-between border-t border-border pt-1 mt-1">
                <span className="font-medium text-sm">Total</span>
                <span className="font-bold text-sm">{displayWeight(localMaxes.squat + localMaxes.bench + localMaxes.deadlift, unit)}</span>
              </div>
            </div>
          ) : (
            <div className="space-y-1 text-sm">
              <div className="flex justify-between"><span>Squat</span><span className="font-medium">{displayWeight(meta.target_squat_kg, unit)}</span></div>
              <div className="flex justify-between"><span>Bench</span><span className="font-medium">{displayWeight(meta.target_bench_kg, unit)}</span></div>
              <div className="flex justify-between"><span>Deadlift</span><span className="font-medium">{displayWeight(meta.target_dl_kg, unit)}</span></div>
              <div className="flex justify-between border-t border-border pt-1 mt-1">
                <span className="font-medium">Total</span>
                <span className="font-bold">{displayWeight(meta.target_total_kg, unit)}</span>
              </div>
            </div>
          )}
        </div>

        {/* Actual Maxes */}
        {(actualMaxes.squat > 0 || actualMaxes.bench > 0 || actualMaxes.deadlift > 0) && (
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Actual Maxes</h3>
            </div>
            <div className="space-y-2 text-sm">
              {[
                { label: 'Squat', actual: actualMaxes.squat, target: meta.target_squat_kg },
                { label: 'Bench', actual: actualMaxes.bench, target: meta.target_bench_kg },
                { label: 'Deadlift', actual: actualMaxes.deadlift, target: meta.target_dl_kg },
              ].map(({ label, actual, target }) =>
                actual > 0 ? (
                  <div key={label}>
                    <div className="flex justify-between mb-0.5">
                      <span>{label}: {displayWeight(actual, unit)}</span>
                      <span className="text-muted-foreground">Target: {displayWeight(target, unit)}</span>
                    </div>
                    <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                      <div className={`h-full rounded-full transition-all ${actual >= target ? 'bg-green-500' : 'bg-primary'}`}
                        style={{ width: `${Math.min(100, (actual / target) * 100)}%` }} />
                    </div>
                  </div>
                ) : null
              )}
              {(actualMaxes.squat > 0 || actualMaxes.bench > 0 || actualMaxes.deadlift > 0) && (
                <div className="flex justify-between border-t border-border pt-1 mt-1">
                  <span className="font-medium">Total</span>
                  <span className="font-bold">{displayWeight(actualMaxes.squat + actualMaxes.bench + actualMaxes.deadlift, unit)}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Body Weight */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Scale className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Body Weight</h3>
            </div>
            {editingWeight ? (
              <div className="flex gap-1">
                <button onClick={saveWeight} className="p-1 hover:bg-accent rounded text-primary"><Save className="w-4 h-4" /></button>
                <button onClick={() => setEditingWeight(false)} className="p-1 hover:bg-accent rounded"><X className="w-4 h-4" /></button>
              </div>
            ) : (
              <button onClick={startEditingWeight} className="p-1 hover:bg-accent rounded"><Edit2 className="w-4 h-4 text-muted-foreground" /></button>
            )}
          </div>
          {editingWeight ? (
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.1"
                value={toDisplayUnit(localWeight, unit)}
                onChange={(e) => setLocalWeight(fromDisplayUnit(Number(e.target.value), unit))}
                className="flex-1 px-2 py-1 border border-border rounded bg-background text-2xl font-bold"
              />
              <span className="text-sm text-muted-foreground">{unit}</span>
            </div>
          ) : (
            <p className="text-3xl font-bold">{displayWeight(latestWeightKg, unit)}</p>
          )}
          <p className="text-sm text-muted-foreground">Target: {meta.weight_class_kg} kg class</p>
          <div className="mt-2 h-2 bg-secondary rounded-full overflow-hidden">
            <div className="h-full bg-primary transition-all" style={{ width: `${Math.min(100, (latestWeightKg / meta.weight_class_kg) * 100)}%` }} />
          </div>
        </div>

        {/* This Week */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <CalendarDays className="w-5 h-5 text-primary" />
            <h3 className="font-medium">This Week</h3>
          </div>
          <p className="text-3xl font-bold">{completedThisWeek}/{thisWeekSessions.length}</p>
          <p className="text-sm text-muted-foreground">sessions completed</p>
        </div>

        {/* Current Phase */}
        {currentPhase && (
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Current Phase</h3>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: phaseColor(currentPhase, phases) }} />
              <span className="font-medium">{currentPhase.name}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">{currentPhase.intent}</p>
          </div>
        )}

        {/* Program Phases */}
        <div className="bg-card border border-border rounded-lg p-4 col-span-1 md:col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Program Phases</h3>
            </div>
            {editingPhases ? (
              <div className="flex gap-1">
                <button onClick={addPhase} className="p-1 hover:bg-accent rounded text-primary"><Plus className="w-4 h-4" /></button>
                <button onClick={savePhases} className="p-1 hover:bg-accent rounded text-primary"><Save className="w-4 h-4" /></button>
                <button onClick={() => setEditingPhases(false)} className="p-1 hover:bg-accent rounded"><X className="w-4 h-4" /></button>
              </div>
            ) : (
              <button onClick={startEditingPhases} className="p-1 hover:bg-accent rounded"><Edit2 className="w-4 h-4 text-muted-foreground" /></button>
            )}
          </div>
          {editingPhases ? (
            <div className="space-y-2">
              {localPhases.map((phase, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2 bg-secondary/50 rounded">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: phaseColor(phase, localPhases) }} />
                  <input type="text" value={phase.name} onChange={(e) => updatePhase(idx, 'name', e.target.value)}
                    placeholder="Phase name" className="flex-1 px-2 py-1 border border-border rounded bg-background text-xs" />
                  <input type="number" value={phase.start_week} onChange={(e) => updatePhase(idx, 'start_week', Number(e.target.value))}
                    className="w-12 px-1 py-1 border border-border rounded bg-background text-xs text-center" />
                  <span className="text-xs">-</span>
                  <input type="number" value={phase.end_week} onChange={(e) => updatePhase(idx, 'end_week', Number(e.target.value))}
                    className="w-12 px-1 py-1 border border-border rounded bg-background text-xs text-center" />
                  <button onClick={() => removePhase(idx)} className="p-1 text-destructive hover:bg-destructive/10 rounded"><Trash2 className="w-3 h-3" /></button>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {phases.map((phase, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: phaseColor(phase, phases) }} />
                  <span className="text-sm">W{phase.start_week}-W{phase.end_week}: {phase.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Lift Profiles Section */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Dumbbell className="w-5 h-5 text-primary" />
            <h3 className="font-medium">Lift Style Profiles</h3>
          </div>
          {editingLiftProfiles ? (
            <div className="flex gap-1">
              <button onClick={saveLiftProfiles} className="p-1 hover:bg-accent rounded text-primary"><Save className="w-4 h-4" /></button>
              <button onClick={() => setEditingLiftProfiles(false)} className="p-1 hover:bg-accent rounded"><X className="w-4 h-4" /></button>
            </div>
          ) : (
            <button onClick={startEditingLiftProfiles} className="p-1 hover:bg-accent rounded"><Edit2 className="w-4 h-4 text-muted-foreground" /></button>
          )}
        </div>

        {editingLiftProfiles ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {localLiftProfiles.map((profile) => (
              <div key={profile.lift} className="space-y-3">
                <h4 className="font-medium text-sm capitalize border-b border-border pb-1">{LIFT_LABELS[profile.lift]}</h4>

                {/* Style Notes */}
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Style & Setup</label>
                  <textarea
                    value={profile.style_notes}
                    onChange={(e) => updateLocalProfile(profile.lift, { style_notes: e.target.value })}
                    rows={3}
                    className="w-full px-2 py-1.5 border border-border rounded bg-background text-xs resize-none"
                    placeholder={LIFT_STYLE_PLACEHOLDERS[profile.lift]}
                  />
                </div>

                {/* Sticking Points */}
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Sticking Points</label>
                  <textarea
                    value={profile.sticking_points}
                    onChange={(e) => updateLocalProfile(profile.lift, { sticking_points: e.target.value })}
                    rows={2}
                    className="w-full px-2 py-1.5 border border-border rounded bg-background text-xs resize-none"
                    placeholder={STICKING_PLACEHOLDERS[profile.lift]}
                  />
                </div>

                {/* Primary Muscle */}
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Primary Muscle Driving the Lift</label>
                  <input
                    type="text"
                    value={profile.primary_muscle}
                    onChange={(e) => updateLocalProfile(profile.lift, { primary_muscle: e.target.value })}
                    className="w-full px-2 py-1.5 border border-border rounded bg-background text-xs"
                    placeholder={profile.lift === 'squat' ? 'e.g. Quad dominant' : profile.lift === 'bench' ? 'e.g. Tricep dominant' : 'e.g. Glute dominant'}
                  />
                </div>

                {/* Volume Tolerance */}
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Volume Recovery Tolerance</label>
                  <div className="flex gap-2">
                    {(['low', 'moderate', 'high'] as const).map((level) => (
                      <button
                        key={level}
                        onClick={() => updateLocalProfile(profile.lift, { volume_tolerance: level })}
                        className={`flex-1 py-1.5 rounded text-xs font-medium capitalize border transition-colors ${
                          profile.volume_tolerance === level
                            ? level === 'low'
                              ? 'bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800'
                              : level === 'moderate'
                                ? 'bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800'
                                : 'bg-green-100 text-green-700 border-green-300 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800'
                            : 'bg-background text-muted-foreground border-border hover:bg-accent'
                        }`}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {displayProfiles.map((profile) => {
              const hasData = profile.style_notes || profile.sticking_points || profile.primary_muscle
              return (
                <div key={profile.lift} className="space-y-2">
                  <h4 className="font-medium text-sm capitalize border-b border-border pb-1">{LIFT_LABELS[profile.lift]}</h4>
                  {hasData ? (
                    <>
                      {profile.style_notes && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-0.5">Style</p>
                          <p className="text-xs leading-relaxed">{profile.style_notes}</p>
                        </div>
                      )}
                      {profile.sticking_points && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-0.5">Sticking Points</p>
                          <p className="text-xs leading-relaxed text-orange-600 dark:text-orange-400">{profile.sticking_points}</p>
                        </div>
                      )}
                      {profile.primary_muscle && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-0.5">Primary Driver</p>
                          <p className="text-xs font-medium">{profile.primary_muscle}</p>
                        </div>
                      )}
                      <div>
                        <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
                          profile.volume_tolerance === 'low'
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                            : profile.volume_tolerance === 'moderate'
                              ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                              : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        }`}>
                          {profile.volume_tolerance} volume tolerance
                        </span>
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No profile yet — click edit to add</p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
