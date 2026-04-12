import { useState, useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Trash2, X, Save } from 'lucide-react'
import { clsx } from 'clsx'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import * as api from '@/api/client'
import type { Session, PlannedExercise, GlossaryExercise } from '@powerlifting/types'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export default function DesignerPage() {
  const { program, version, createSession } = useProgramStore()
  const { pushToast } = useUiStore()
  const [searchParams] = useSearchParams()

  const [block, setBlock] = useState('current')
  const [selectedWeek, setSelectedWeek] = useState(1)
  const [editingSession, setEditingSession] = useState<Session | null>(null)
  const [editingSessionGlobalIndex, setEditingSessionGlobalIndex] = useState<number>(-1)
  const [editingSessionDate, setEditingSessionDate] = useState<string>('')
  const [isSessionEditorOpen, setIsSessionEditorOpen] = useState(false)
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [exerciseSearch, setExerciseSearch] = useState('')

  // Session form state
  const [sessionDate, setSessionDate] = useState('')
  const [sessionDay, setSessionDay] = useState('Monday')
  const [sessionWeek, setSessionWeek] = useState('W1')
  const [sessionPhase, setSessionPhase] = useState('')
  const [plannedExercises, setPlannedExercises] = useState<PlannedExercise[]>([])

  const phases = program?.phases || []

  useEffect(() => {
    api.fetchGlossary().then(setGlossary).catch(console.error)
  }, [])

  // Read week from URL query params
  useEffect(() => {
    const weekParam = searchParams.get('week')
    if (weekParam) {
      const week = parseInt(weekParam, 10)
      if (!isNaN(week) && week > 0) {
        setSelectedWeek(week)
      }
    }
  }, [searchParams])

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

  function openSessionEditor(session?: Session, date?: string, index?: number) {
    if (session) {
      setEditingSession(session)
      setEditingSessionDate(session.date)
      setEditingSessionGlobalIndex(
        index !== undefined && index >= 0
          ? program?.sessions.indexOf(session) ?? -1
          : program?.sessions.findIndex(s => s.date === session.date && s.week_number === session.week_number && s.day === session.day) ?? -1
      )
      setSessionDate(session.date)
      setSessionDay(session.day)
      setSessionWeek(session.week)
      setSessionPhase(typeof session.phase === 'string' ? session.phase : session.phase?.name || '')
      setPlannedExercises(session.planned_exercises || [])
    } else {
      setEditingSession(null)
      setEditingSessionDate('')
      setEditingSessionGlobalIndex(-1)
      const dayName = DAYS[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]
      setSessionDate(new Date().toISOString().slice(0, 10))
      setSessionDay(dayName)
      setSessionWeek(`W${selectedWeek}`)
      // Use phase from URL if provided, otherwise first phase
      const phaseParam = searchParams.get('phase')
      setSessionPhase(phaseParam || phases[0]?.name || '')
      setPlannedExercises([])
    }
    setIsSessionEditorOpen(true)
  }

  function closeSessionEditor() {
    setEditingSession(null)
    setEditingSessionDate('')
    setEditingSessionGlobalIndex(-1)
    setIsSessionEditorOpen(false)
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
        if (editingSessionGlobalIndex < 0) {
          throw new Error('Could not resolve the session index for update')
        }
        await api.updatePlannedExercises(version, editingSessionDate, editingSessionGlobalIndex, plannedExercises)
      } else {
        await createSession(sessionData)
      }

      closeSessionEditor()
      useProgramStore.getState().loadProgram(version)
    } catch (err) {
      console.error('Failed to save session:', err)
      pushToast({ message: 'Failed to save session', type: 'error' })
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

  const filteredGlossary = useMemo(() => {
    if (!exerciseSearch.trim()) return glossary.slice(0, 10)
    const q = exerciseSearch.toLowerCase()
    return glossary.filter(e => e.name.toLowerCase().includes(q)).slice(0, 10)
  }, [glossary, exerciseSearch])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link to="/designer" className="text-muted-foreground hover:text-foreground text-sm">Designer</Link>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-2xl font-bold">Session Design</h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
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

      {/* Session cards */}
      {weekSessions.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
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

      {/* Session Editor Modal */}
      {isSessionEditorOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={closeSessionEditor}>
          <div className="bg-card border border-border rounded-lg w-[calc(100%-1rem)] sm:w-full max-w-2xl max-h-[85vh] overflow-y-auto p-4 sm:p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{editingSession ? 'Edit Session' : 'Plan Session'}</h3>
              <button onClick={closeSessionEditor} className="p-1 hover:bg-accent rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                <div key={i} className="mb-2.5 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium truncate">{ex.name}</span>
                    <button onClick={() => removePlannedExercise(i)} className="p-1 text-destructive hover:bg-accent rounded shrink-0">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="number"
                      value={ex.sets}
                      onChange={(e) => updatePlannedExercise(i, 'sets', Number(e.target.value))}
                      className="w-14 px-2 py-1 border border-border rounded bg-background text-sm text-center"
                      placeholder="Sets"
                    />
                    <span className="text-xs text-muted-foreground">x</span>
                    <input
                      type="number"
                      value={ex.reps}
                      onChange={(e) => updatePlannedExercise(i, 'reps', Number(e.target.value))}
                      className="w-14 px-2 py-1 border border-border rounded bg-background text-sm text-center"
                      placeholder="Reps"
                    />
                    <span className="text-xs text-muted-foreground">@</span>
                    <input
                      type="number"
                      value={ex.kg ?? ''}
                      onChange={(e) => updatePlannedExercise(i, 'kg', e.target.value ? Number(e.target.value) : null)}
                      className="w-16 px-2 py-1 border border-border rounded bg-background text-sm text-center"
                      placeholder="kg"
                    />
                  </div>
                </div>
              ))}

              {/* Add exercise */}
              <div className="relative mt-2">
                <input
                  type="text"
                  value={exerciseSearch}
                  onChange={(e) => setExerciseSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && filteredGlossary.length > 0) {
                      e.preventDefault()
                      addPlannedExercise(filteredGlossary[0])
                    }
                  }}
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
                <p className="text-xs text-muted-foreground mt-1">Press Enter to add the first match.</p>
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
    </div>
  )
}
