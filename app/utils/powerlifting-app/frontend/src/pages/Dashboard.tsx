import { useState } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { daysUntil, formatDateShort, sessionsThisCalendarWeek } from '@/utils/dates'
import { displayWeight, toDisplayUnit, fromDisplayUnit } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import { CalendarDays, Target, Scale, Trophy, TrendingUp, Edit2, Save, X, Plus, Trash2 } from 'lucide-react'
import type { Phase } from '@powerlifting/types'

export default function Dashboard() {
  const { program, isLoading, updateMaxes, updateBodyWeight, updatePhases } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()

  const [editingMaxes, setEditingMaxes] = useState(false)
  const [editingWeight, setEditingWeight] = useState(false)
  const [editingPhases, setEditingPhases] = useState(false)
  const [localMaxes, setLocalMaxes] = useState({ squat: 0, bench: 0, deadlift: 0 })
  const [localWeight, setLocalWeight] = useState(0)
  const [localPhases, setLocalPhases] = useState<Phase[]>([])

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

  // Get next competition
  const upcomingComps = competitions
    .filter((c) => c.status !== 'skipped' && new Date(c.date) >= new Date())
    .sort((a, b) => a.date.localeCompare(b.date))
  const nextComp = upcomingComps[0]

  // Current phase from first session this week (if any)
  const currentPhase = thisWeekSessions[0]?.phase

  const startEditingMaxes = () => {
    setLocalMaxes({
      squat: meta.target_squat_kg,
      bench: meta.target_bench_kg,
      deadlift: meta.target_dl_kg,
    })
    setEditingMaxes(true)
  }

  const saveMaxes = async () => {
    try {
      await updateMaxes({
        squat_kg: localMaxes.squat,
        bench_kg: localMaxes.bench,
        deadlift_kg: localMaxes.deadlift,
      })
      pushToast({ message: 'Target maxes updated', type: 'success' })
      setEditingMaxes(false)
    } catch (err) {
      pushToast({ message: 'Failed to update maxes', type: 'error' })
    }
  }

  const startEditingWeight = () => {
    setLocalWeight(meta.current_body_weight_kg)
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
    setLocalPhases(prev => [...prev, {
      name: 'New Phase',
      intent: '',
      start_week: newStart,
      end_week: newStart + 3,
    }])
  }

  const removePhase = (index: number) => {
    setLocalPhases(prev => prev.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Competition Countdown */}
        {nextComp && (
          <div className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Trophy className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Next Competition</h3>
            </div>
            <p className="text-3xl font-bold">{daysUntil(nextComp.date)}</p>
            <p className="text-sm text-muted-foreground">days until {nextComp.name}</p>
          </div>
        )}

        {/* Current Maxes - EDITABLE */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Target Maxes</h3>
            </div>
            {editingMaxes ? (
              <div className="flex gap-1">
                <button onClick={saveMaxes} className="p-1 hover:bg-accent rounded text-primary">
                  <Save className="w-4 h-4" />
                </button>
                <button onClick={() => setEditingMaxes(false)} className="p-1 hover:bg-accent rounded">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button onClick={startEditingMaxes} className="p-1 hover:bg-accent rounded">
                <Edit2 className="w-4 h-4 text-muted-foreground" />
              </button>
            )}
          </div>
          {editingMaxes ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="w-16 text-sm">Squat</span>
                <input
                  type="number"
                  value={toDisplayUnit(localMaxes.squat, unit)}
                  onChange={(e) => setLocalMaxes(prev => ({ ...prev, squat: fromDisplayUnit(Number(e.target.value), unit) }))}
                  className="flex-1 px-2 py-1 border border-border rounded bg-background text-sm"
                />
                <span className="text-xs text-muted-foreground">{unit}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-16 text-sm">Bench</span>
                <input
                  type="number"
                  value={toDisplayUnit(localMaxes.bench, unit)}
                  onChange={(e) => setLocalMaxes(prev => ({ ...prev, bench: fromDisplayUnit(Number(e.target.value), unit) }))}
                  className="flex-1 px-2 py-1 border border-border rounded bg-background text-sm"
                />
                <span className="text-xs text-muted-foreground">{unit}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-16 text-sm">Deadlift</span>
                <input
                  type="number"
                  value={toDisplayUnit(localMaxes.deadlift, unit)}
                  onChange={(e) => setLocalMaxes(prev => ({ ...prev, deadlift: fromDisplayUnit(Number(e.target.value), unit) }))}
                  className="flex-1 px-2 py-1 border border-border rounded bg-background text-sm"
                />
                <span className="text-xs text-muted-foreground">{unit}</span>
              </div>
              <div className="flex justify-between border-t border-border pt-1 mt-1">
                <span className="font-medium text-sm">Total</span>
                <span className="font-bold text-sm">{displayWeight(localMaxes.squat + localMaxes.bench + localMaxes.deadlift, unit)}</span>
              </div>
            </div>
          ) : (
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span>Squat</span>
                <span className="font-medium">{displayWeight(meta.target_squat_kg, unit)}</span>
              </div>
              <div className="flex justify-between">
                <span>Bench</span>
                <span className="font-medium">{displayWeight(meta.target_bench_kg, unit)}</span>
              </div>
              <div className="flex justify-between">
                <span>Deadlift</span>
                <span className="font-medium">{displayWeight(meta.target_dl_kg, unit)}</span>
              </div>
              <div className="flex justify-between border-t border-border pt-1 mt-1">
                <span className="font-medium">Total</span>
                <span className="font-bold">{displayWeight(meta.target_total_kg, unit)}</span>
              </div>
            </div>
          )}
        </div>

        {/* Weight vs Class - EDITABLE */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Scale className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Body Weight</h3>
            </div>
            {editingWeight ? (
              <div className="flex gap-1">
                <button onClick={saveWeight} className="p-1 hover:bg-accent rounded text-primary">
                  <Save className="w-4 h-4" />
                </button>
                <button onClick={() => setEditingWeight(false)} className="p-1 hover:bg-accent rounded">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button onClick={startEditingWeight} className="p-1 hover:bg-accent rounded">
                <Edit2 className="w-4 h-4 text-muted-foreground" />
              </button>
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
            <p className="text-3xl font-bold">
              {displayWeight(meta.current_body_weight_kg, unit)}
            </p>
          )}
          <p className="text-sm text-muted-foreground">
            Target: {meta.weight_class_kg} kg class
          </p>
          <div className="mt-2 h-2 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all"
              style={{
                width: `${Math.min(
                  100,
                  (meta.current_body_weight_kg / meta.weight_class_kg) * 100
                )}%`,
              }}
            />
          </div>
        </div>

        {/* This Week's Sessions */}
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <CalendarDays className="w-5 h-5 text-primary" />
            <h3 className="font-medium">This Week</h3>
          </div>
          <p className="text-3xl font-bold">
            {completedThisWeek}/{thisWeekSessions.length}
          </p>
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
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: phaseColor(currentPhase, phases) }}
              />
              <span className="font-medium">{currentPhase.name}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              {currentPhase.intent}
            </p>
          </div>
        )}

        {/* Program Progress / Phases - EDITABLE */}
        <div className="bg-card border border-border rounded-lg p-4 col-span-1 md:col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3 className="font-medium">Program Phases</h3>
            </div>
            {editingPhases ? (
              <div className="flex gap-1">
                <button onClick={addPhase} className="p-1 hover:bg-accent rounded text-primary">
                  <Plus className="w-4 h-4" />
                </button>
                <button onClick={savePhases} className="p-1 hover:bg-accent rounded text-primary">
                  <Save className="w-4 h-4" />
                </button>
                <button onClick={() => setEditingPhases(false)} className="p-1 hover:bg-accent rounded">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <button onClick={startEditingPhases} className="p-1 hover:bg-accent rounded">
                <Edit2 className="w-4 h-4 text-muted-foreground" />
              </button>
            )}
          </div>
          {editingPhases ? (
            <div className="space-y-2">
              {localPhases.map((phase, idx) => (
                <div key={idx} className="flex items-center gap-2 p-2 bg-secondary/50 rounded">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: phaseColor(phase, localPhases) }}
                  />
                  <input
                    type="text"
                    value={phase.name}
                    onChange={(e) => updatePhase(idx, 'name', e.target.value)}
                    placeholder="Phase name"
                    className="flex-1 px-2 py-1 border border-border rounded bg-background text-xs"
                  />
                  <input
                    type="number"
                    value={phase.start_week}
                    onChange={(e) => updatePhase(idx, 'start_week', Number(e.target.value))}
                    className="w-12 px-1 py-1 border border-border rounded bg-background text-xs text-center"
                  />
                  <span className="text-xs">-</span>
                  <input
                    type="number"
                    value={phase.end_week}
                    onChange={(e) => updatePhase(idx, 'end_week', Number(e.target.value))}
                    className="w-12 px-1 py-1 border border-border rounded bg-background text-xs text-center"
                  />
                  <button onClick={() => removePhase(idx)} className="p-1 text-destructive hover:bg-destructive/10 rounded">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {phases.map((phase, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: phaseColor(phase, phases) }}
                  />
                  <span className="text-sm">W{phase.start_week}-W{phase.end_week}: {phase.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
