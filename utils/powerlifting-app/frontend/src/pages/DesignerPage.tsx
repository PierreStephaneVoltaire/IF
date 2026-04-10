import { useState, useEffect, useMemo } from 'react'
import { Plus, Edit2, Trash2, X, ChevronRight, Save } from 'lucide-react'
import { clsx } from 'clsx'
import { useProgramStore } from '@/store/programStore'
import * as api from '@/api/client'
import type { Phase, Session, PlannedExercise, GlossaryExercise } from '@powerlifting/types'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export default function DesignerPage() {
  const { program, version, createSession, updatePhases } = useProgramStore()

  const [block, setBlock] = useState('current')
  const [selectedPhaseIndex, setSelectedPhaseIndex] = useState(0)
  const [selectedWeek, setSelectedWeek] = useState(1)
  const [editingSession, setEditingSession] = useState<Session | null>(null)
  const [editingSessionDate, setEditingSessionDate] = useState<string>('')
  const [editingSessionIdx, setEditingSessionIdx] = useState<number>(-1)
  const [editingPhase, setEditingPhase] = useState<Phase | null>(null)
  const [editingPhaseIndex, setEditingPhaseIndex] = useState<number>(-1)
  const [isNewPhase, setIsNewPhase] = useState(false)
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [exerciseSearch, setExerciseSearch] = useState('')

  // Session form state
  const [sessionDate, setSessionDate] = useState('')
  const [sessionDay, setSessionDay] = useState('Monday')
  const [sessionWeek, setSessionWeek] = useState('W1')
  const [sessionPhase, setSessionPhase] = useState('')
  const [plannedExercises, setPlannedExercises] = useState<PlannedExercise[]>([])

  // Phase form state
  const [phaseForm, setPhaseForm] = useState<Partial<Phase>>({
    name: '',
    intent: '',
    start_week: 1,
    end_week: 4,
    target_rpe_min: 6,
    target_rpe_max: 8,
    days_per_week: 4,
    notes: '',
  })

  useEffect(() => {
    api.fetchGlossary().then(setGlossary).catch(console.error)
  }, [])

  const phases = program?.phases || []
  const selectedPhase = phases[selectedPhaseIndex] || null

  const totalWeeks = useMemo(() => {
    if (!phases.length) return 12
    return Math.max(...phases.map(p => p.end_week))
  }, [phases])

  const weekOptions = useMemo(() => {
    return Array.from({ length: totalWeeks }, (_, i) => i + 1)
  }, [totalWeeks])

  const blocks = useMemo(() => {
    const s = new Set<string>()
    for (const session of (program?.sessions || [])) s.add(session.block ?? 'current')
    return Array.from(s)
  }, [program?.sessions])

  const weekSessions = useMemo(() => {
    return (program?.sessions || [])
      .filter(s => s.week_number === selectedWeek)
      .filter(s => (s.block ?? 'current') === block)
  }, [program?.sessions, selectedWeek, block])

  // Set selected week to match selected phase
  useEffect(() => {
    if (selectedPhase) {
      setSelectedWeek(selectedPhase.start_week)
    }
  }, [selectedPhaseIndex])

  function openSessionEditor(session?: Session, date?: string, index?: number) {
    if (session) {
      setEditingSession(session)
      setEditingSessionDate(session.date)
      setEditingSessionIdx(index ?? -1)
      setSessionDate(session.date)
      setSessionDay(session.day)
      setSessionWeek(session.week)
      setSessionPhase(typeof session.phase === 'string' ? session.phase : session.phase?.name || '')
      setPlannedExercises(session.planned_exercises || [])
    } else {
      setEditingSession(null)
      setEditingSessionDate('')
      setEditingSessionIdx(-1)
      const dayName = DAYS[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]
      setSessionDate(new Date().toISOString().slice(0, 10))
      setSessionDay(dayName)
      setSessionWeek(`W${selectedWeek}`)
      setSessionPhase(selectedPhase?.name || '')
      setPlannedExercises([])
    }
  }

  function closeSessionEditor() {
    setEditingSession(null)
    setEditingSessionDate('')
    setEditingSessionIdx(-1)
    setPlannedExercises([])
    setExerciseSearch('')
  }

  async function saveSession() {
    try {
      const sessionData: Partial<Session> & { date: string } = {
        date: sessionDate,
        day: sessionDay,
        week: sessionWeek,
        status: 'planned',
        completed: false,
        planned_exercises: plannedExercises,
        exercises: [],
        session_notes: '',
      }

      if (editingSession) {
        await api.updateSession(version, editingSessionDate, editingSessionIdx, {
          ...editingSession,
          planned_exercises: plannedExercises,
        })
      } else {
        await createSession(sessionData)
      }

      closeSessionEditor()
      useProgramStore.getState().loadProgram(version)
    } catch (err) {
      console.error('Failed to save session:', err)
    }
  }

  function addPlannedExercise(exercise: GlossaryExercise) {
    setPlannedExercises(prev => [...prev, {
      name: exercise.name,
      sets: 3,
      reps: 5,
      kg: null,
    }])
    setExerciseSearch('')
  }

  function updatePlannedExercise(index: number, field: keyof PlannedExercise, value: unknown) {
    setPlannedExercises(prev => prev.map((pe, i) => i === index ? { ...pe, [field]: value } : pe))
  }

  function removePlannedExercise(index: number) {
    setPlannedExercises(prev => prev.filter((_, i) => i !== index))
  }

  function openPhaseEditor(phase?: Phase, index?: number) {
    if (phase && index !== undefined) {
      setEditingPhase(phase)
      setEditingPhaseIndex(index)
      setIsNewPhase(false)
      setPhaseForm({ ...phase })
    } else {
      setEditingPhase(null)
      setEditingPhaseIndex(-1)
      setIsNewPhase(true)
      setPhaseForm({
        name: '',
        intent: '',
        start_week: totalWeeks + 1,
        end_week: totalWeeks + 4,
        target_rpe_min: 6,
        target_rpe_max: 8,
        days_per_week: 4,
        notes: '',
      })
    }
  }

  function closePhaseEditor() {
    setEditingPhase(null)
    setEditingPhaseIndex(-1)
    setIsNewPhase(false)
  }

  async function savePhase() {
    const updatedPhases = [...phases]
    const phaseData: Phase = {
      name: phaseForm.name || 'Unnamed',
      intent: phaseForm.intent || '',
      start_week: phaseForm.start_week || 1,
      end_week: phaseForm.end_week || 4,
      target_rpe_min: phaseForm.target_rpe_min,
      target_rpe_max: phaseForm.target_rpe_max,
      days_per_week: phaseForm.days_per_week,
      notes: phaseForm.notes,
    }

    if (editingPhaseIndex >= 0) {
      updatedPhases[editingPhaseIndex] = phaseData
    } else {
      updatedPhases.push(phaseData)
    }

    updatedPhases.sort((a, b) => a.start_week - b.start_week)

    await updatePhases(updatedPhases)
    const newIdx = updatedPhases.findIndex(p => p.name === phaseData.name)
    if (newIdx >= 0) setSelectedPhaseIndex(newIdx)
    closePhaseEditor()
  }

  async function deletePhase(name: string) {
    if (!confirm(`Delete phase "${name}"?`)) return
    const updatedPhases = phases.filter(p => p.name !== name)
    await updatePhases(updatedPhases)
  }

  const filteredGlossary = useMemo(() => {
    if (!exerciseSearch.trim()) return glossary.slice(0, 10)
    const q = exerciseSearch.toLowerCase()
    return glossary.filter(e => e.name.toLowerCase().includes(q)).slice(0, 10)
  }, [glossary, exerciseSearch])

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0">
      {/* Left sidebar — Phase list */}
      <div className="w-64 border-r border-border flex flex-col">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold">Phases</h2>
          <button
            onClick={() => openPhaseEditor()}
            className="p-1 hover:bg-accent rounded"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {phases.map((phase, i) => (
            <button
              key={phase.name}
              onClick={() => setSelectedPhaseIndex(i)}
              className={clsx(
                'w-full text-left px-4 py-3 border-b border-border/50 hover:bg-accent/50',
                i === selectedPhaseIndex && 'bg-accent'
              )}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">{phase.name}</p>
                  <p className="text-xs text-muted-foreground">
                    W{phase.start_week} - W{phase.end_week}
                  </p>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); openPhaseEditor(phase, i) }}
                    className="p-1 hover:bg-accent rounded"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); deletePhase(phase.name) }}
                    className="p-1 hover:bg-accent rounded text-destructive"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </button>
          ))}
          {phases.length === 0 && (
            <p className="text-sm text-muted-foreground p-4">No phases defined. Click + to add one.</p>
          )}
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Program Designer</h1>
          <div className="flex items-center gap-3">
            {blocks.length > 1 && (
              <select
                value={block}
                onChange={(e) => setBlock(e.target.value)}
                className="px-3 py-1.5 border border-border rounded-md bg-background text-sm"
              >
                {blocks.map(b => (
                  <option key={b} value={b}>{b === 'current' ? 'Current Block' : b}</option>
                ))}
              </select>
            )}
            <select
              value={selectedWeek}
              onChange={(e) => setSelectedWeek(Number(e.target.value))}
              className="px-3 py-1.5 border border-border rounded-md bg-background text-sm"
            >
              {weekOptions.map(w => (
                <option key={w} value={w}>Week {w}</option>
              ))}
            </select>
            <button
              onClick={() => openSessionEditor()}
              className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm"
            >
              <Plus className="w-4 h-4" />
              Add Session
            </button>
          </div>
        </div>

        {selectedPhase && (
          <p className="text-sm text-muted-foreground">
            {selectedPhase.name} &middot; W{selectedPhase.start_week}-W{selectedPhase.end_week}
            {selectedPhase.target_rpe_min && selectedPhase.target_rpe_max && (
              <> &middot; RPE {selectedPhase.target_rpe_min}-{selectedPhase.target_rpe_max}</>
            )}
            {selectedPhase.days_per_week && <> &middot; {selectedPhase.days_per_week}x/week</>}
          </p>
        )}

        {/* Session cards */}
        {weekSessions.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {weekSessions.map((session, i) => (
              <div
                key={`${session.date}-${i}`}
                className="bg-card border border-border rounded-lg p-4 cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => openSessionEditor(session, session.date, i)}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{session.day}</span>
                  <span className={clsx(
                    'text-xs px-2 py-0.5 rounded',
                    session.status === 'planned' && 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
                    session.status === 'completed' && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
                    session.status === 'logged' && 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
                    session.status === 'skipped' && 'bg-gray-100 text-gray-500',
                  )}>
                    {session.status || 'planned'}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mb-3">{session.date}</p>

                {(session.planned_exercises || []).length > 0 ? (
                  <div className="space-y-1">
                    {session.planned_exercises!.map((ex, j) => (
                      <div key={j} className="flex items-center justify-between text-sm">
                        <span>{ex.name}</span>
                        <span className="text-muted-foreground">
                          {ex.sets}x{ex.reps}{ex.kg ? ` @${ex.kg}kg` : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No exercises planned</p>
                )}

                {session.exercises?.length > 0 && (
                  <p className="text-xs text-muted-foreground mt-2 border-t border-border/50 pt-2">
                    {session.exercises.length} exercises logged
                  </p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center py-12">
            <p className="text-muted-foreground">No sessions for Week {selectedWeek}. Click "Add Session" to plan one.</p>
          </div>
        )}
      </div>

      {/* Session Editor Modal */}
      {editingSession !== null || editingSessionDate !== '' ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={closeSessionEditor}>
          <div className="bg-card border border-border rounded-lg w-full max-w-lg max-h-[80vh] overflow-y-auto p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{editingSession ? 'Edit Session' : 'Plan Session'}</h3>
              <button onClick={closeSessionEditor} className="p-1 hover:bg-accent rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-muted-foreground">Date</label>
                <input
                  type="date"
                  value={sessionDate}
                  onChange={(e) => setSessionDate(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Day</label>
                <select
                  value={sessionDay}
                  onChange={(e) => setSessionDay(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                >
                  {DAYS.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-muted-foreground">Week</label>
                <input
                  type="text"
                  value={sessionWeek}
                  onChange={(e) => setSessionWeek(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Phase</label>
                <select
                  value={sessionPhase}
                  onChange={(e) => setSessionPhase(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                >
                  <option value="">None</option>
                  {phases.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
                </select>
              </div>
            </div>

            {/* Planned exercises */}
            <div>
              <label className="text-sm text-muted-foreground block mb-2">Planned Exercises</label>

              {plannedExercises.map((ex, i) => (
                <div key={i} className="flex items-center gap-2 mb-2">
                  <span className="text-sm flex-1 truncate">{ex.name}</span>
                  <input
                    type="number"
                    value={ex.sets}
                    onChange={(e) => updatePlannedExercise(i, 'sets', Number(e.target.value))}
                    className="w-14 px-2 py-1 border border-border rounded text-sm text-center"
                    placeholder="Sets"
                  />
                  <span className="text-xs text-muted-foreground">x</span>
                  <input
                    type="number"
                    value={ex.reps}
                    onChange={(e) => updatePlannedExercise(i, 'reps', Number(e.target.value))}
                    className="w-14 px-2 py-1 border border-border rounded text-sm text-center"
                    placeholder="Reps"
                  />
                  <span className="text-xs text-muted-foreground">@</span>
                  <input
                    type="number"
                    value={ex.kg ?? ''}
                    onChange={(e) => updatePlannedExercise(i, 'kg', e.target.value ? Number(e.target.value) : null)}
                    className="w-16 px-2 py-1 border border-border rounded text-sm text-center"
                    placeholder="kg"
                  />
                  <button onClick={() => removePlannedExercise(i)} className="p-1 text-destructive hover:bg-accent rounded">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}

              {/* Add exercise */}
              <div className="relative mt-2">
                <input
                  type="text"
                  value={exerciseSearch}
                  onChange={(e) => setExerciseSearch(e.target.value)}
                  placeholder="Search exercises to add..."
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
                {exerciseSearch && filteredGlossary.length > 0 && (
                  <div className="absolute top-full mt-1 w-full bg-card border border-border rounded-md shadow-lg max-h-40 overflow-y-auto z-10">
                    {filteredGlossary.map(ex => (
                      <button
                        key={ex.id}
                        onClick={() => addPlannedExercise(ex)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-accent"
                      >
                        {ex.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={closeSessionEditor} className="px-4 py-2 bg-secondary rounded-md text-sm">
                Cancel
              </button>
              <button onClick={saveSession} className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium">
                <Save className="w-4 h-4" />
                {editingSession ? 'Update' : 'Create'} Session
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Phase Editor Modal */}
      {editingPhase || isNewPhase ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={closePhaseEditor}>
          <div className="bg-card border border-border rounded-lg w-full max-w-md p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{isNewPhase ? 'Add Phase' : 'Edit Phase'}</h3>
              <button onClick={closePhaseEditor} className="p-1 hover:bg-accent rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-sm text-muted-foreground">Name</label>
              <input
                type="text"
                value={phaseForm.name || ''}
                onChange={(e) => setPhaseForm(p => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-muted-foreground">Start Week</label>
                <input
                  type="number"
                  value={phaseForm.start_week || 1}
                  onChange={(e) => setPhaseForm(p => ({ ...p, start_week: Number(e.target.value) }))}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">End Week</label>
                <input
                  type="number"
                  value={phaseForm.end_week || 4}
                  onChange={(e) => setPhaseForm(p => ({ ...p, end_week: Number(e.target.value) }))}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
              </div>
            </div>

            <div>
              <label className="text-sm text-muted-foreground">Intent</label>
              <textarea
                value={phaseForm.intent || ''}
                onChange={(e) => setPhaseForm(p => ({ ...p, intent: e.target.value }))}
                rows={2}
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm resize-none"
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-sm text-muted-foreground">RPE Min</label>
                <input
                  type="number"
                  value={phaseForm.target_rpe_min ?? ''}
                  onChange={(e) => setPhaseForm(p => ({ ...p, target_rpe_min: e.target.value ? Number(e.target.value) : undefined }))}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">RPE Max</label>
                <input
                  type="number"
                  value={phaseForm.target_rpe_max ?? ''}
                  onChange={(e) => setPhaseForm(p => ({ ...p, target_rpe_max: e.target.value ? Number(e.target.value) : undefined }))}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Days/Wk</label>
                <input
                  type="number"
                  value={phaseForm.days_per_week ?? ''}
                  onChange={(e) => setPhaseForm(p => ({ ...p, days_per_week: e.target.value ? Number(e.target.value) : undefined }))}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm"
                />
              </div>
            </div>

            <div>
              <label className="text-sm text-muted-foreground">Notes</label>
              <textarea
                value={phaseForm.notes || ''}
                onChange={(e) => setPhaseForm(p => ({ ...p, notes: e.target.value }))}
                rows={2}
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-sm resize-none"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={closePhaseEditor} className="px-4 py-2 bg-secondary rounded-md text-sm">
                Cancel
              </button>
              <button onClick={savePhase} className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium">
                <Save className="w-4 h-4" />
                {isNewPhase ? 'Add' : 'Update'} Phase
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
