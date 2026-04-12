import { useState, useMemo } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { groupSessionsByWeek, formatDateShort, getDayOfWeek } from '@/utils/dates'
import { displayWeight } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import SessionDrawer from '@/components/sessions/SessionDrawer'
import { Check, ChevronDown, ChevronRight, Dumbbell, Plus, Trash2 } from 'lucide-react'
import type { Session } from '@powerlifting/types'

export default function ListPage() {
  const { program, isLoading, createSession, deleteSession } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()
  const [block, setBlock] = useState('current')

  const availableBlocks = useMemo(() => {
    if (!program) return ['current']
    const blocks = new Set<string>()
    for (const s of program.sessions) blocks.add(s.block ?? 'current')
    return Array.from(blocks).sort()
  }, [program])
  const [expandedWeeks, setExpandedWeeks] = useState<Set<number>>(new Set())
  const [drawerDate, setDrawerDate] = useState<string | null>(null)
  const [drawerArrayIndex, setDrawerArrayIndex] = useState<number | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newDate, setNewDate] = useState<string>('')

  // Get selected session
  const selectedSession = drawerDate
    ? program?.sessions.find((s) => s.date === drawerDate) || null
    : null
  const selectedSessionIndex = drawerDate
    ? program?.sessions.findIndex((s) => s.date === drawerDate) ?? -1
    : -1

  const handleAddSession = async () => {
    if (!newDate) {
      pushToast({ message: 'Please select a date', type: 'error' })
      return
    }

    try {
      const dayOfWeek = getDayOfWeek(newDate)
      await createSession({
        date: newDate,
        day: dayOfWeek,
        exercises: [],
      })
      pushToast({ message: 'Session created', type: 'success' })
      setShowAddModal(false)
      setNewDate('')
      // Open the new session in the drawer — find it by index after reload
      const newIndex = program?.sessions.findIndex(s => s.date === newDate) ?? -1
      setDrawerDate(newDate)
      setDrawerArrayIndex(newIndex >= 0 ? newIndex : null)
    } catch (err) {
      pushToast({ message: 'Failed to create session', type: 'error' })
    }
  }

  const handleDeleteSession = async (date: string, index: number) => {
    if (!confirm('Delete this session?')) return
    try {
      await deleteSession(date, index)
      pushToast({ message: 'Session deleted', type: 'success' })
      setDrawerDate(null)
      setDrawerArrayIndex(null)
    } catch (err) {
      pushToast({ message: 'Failed to delete session', type: 'error' })
    }
  }

  if (isLoading || !program) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    )
  }

  const sessionsByWeek = groupSessionsByWeek(program.sessions, block)

  const toggleWeek = (week: number) => {
    setExpandedWeeks((prev) => {
      const next = new Set(prev)
      if (next.has(week)) {
        next.delete(week)
      } else {
        next.add(week)
      }
      return next
    })
  }

  const handleSessionClick = (date: string, arrayIndex: number) => {
    setDrawerDate(date)
    setDrawerArrayIndex(arrayIndex)
  }

  return (
    <div className="space-y-4 relative">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background py-2 -mx-1 px-1 border-b border-border/50 sm:border-b-0">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <h1 className="text-2xl font-bold">Sessions by Week</h1>
          <div className="flex items-center gap-2">
            {availableBlocks.length > 1 && (
              <select
                value={block}
                onChange={(e) => setBlock(e.target.value)}
                className="px-3 py-1.5 border border-border rounded-md bg-background text-sm"
              >
                {availableBlocks.map((b) => (
                  <option key={b} value={b}>
                    {b === 'current' ? 'Current Block' : b}
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 sm:px-4 sm:py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors text-sm"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Add Session</span>
            </button>
          </div>
        </div>
      </div>

      {/* Floating action button (mobile only) */}
      <button
        onClick={() => setShowAddModal(true)}
        className="fixed bottom-6 right-6 z-40 sm:hidden flex items-center justify-center w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 hover:bg-primary/90 active:scale-95 transition-all"
        aria-label="Add Session"
      >
        <Plus className="w-6 h-6" />
      </button>

      {/* Add Session Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">Add New Session</h2>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">Date</label>
                <input
                  type="date"
                  value={newDate}
                  onChange={(e) => setNewDate(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded bg-background mt-1"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    setShowAddModal(false)
                    setNewDate('')
                  }}
                  className="px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddSession}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                >
                  Create Session
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {Array.from(sessionsByWeek.entries()).map(([week, sessions]) => {
          const firstSession = sessions[0]
          const phase = firstSession?.phase
          const isExpanded = expandedWeeks.has(week)

          return (
            <div key={week} className="border border-border rounded-lg overflow-hidden">
              {/* Week Header */}
              <button
                onClick={() => toggleWeek(week)}
                className="w-full flex items-center gap-3 p-4 bg-card hover:bg-accent transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="w-5 h-5 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-muted-foreground" />
                )}

                {phase && (
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: phaseColor(phase, program.phases) }}
                  />
                )}

                <span className="font-medium">Week {week}</span>
                <span className="text-sm text-muted-foreground">
                  {phase?.name}
                </span>

                <div className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
                  <span>
                    {sessions.filter((s) => s.completed).length}/{sessions.length} completed
                  </span>
                </div>
              </button>

              {/* Session List */}
              {isExpanded && (
                <div className="border-t border-border">
                  {sessions.map((session, arrayIdx) => {
                    const previewExercises = session.exercises.length > 0 ? session.exercises : session.planned_exercises || []
                    const isPlanned = session.exercises.length === 0 && (session.planned_exercises?.length ?? 0) > 0
                    return (
                    <button
                      key={`${session.date}-${arrayIdx}`}
                      onClick={() => handleSessionClick(session.date, program.sessions.indexOf(session))}
                      className="w-full flex items-center gap-3 p-3 hover:bg-accent/50 transition-colors border-b border-border last:border-b-0"
                    >
                      <div className="w-8 h-8 rounded-full flex items-center justify-center bg-secondary">
                        {session.completed ? (
                          <Check className="w-4 h-4 text-primary" />
                        ) : (
                          <Dumbbell className="w-4 h-4 text-muted-foreground" />
                        )}
                      </div>

                      <div className="flex-1 text-left">
                        <div className="font-medium">{session.day}</div>
                        <div className="text-sm text-muted-foreground">
                          {formatDateShort(session.date)}
                        </div>
                      </div>

                      <div className="flex-1 text-right">
                        <div className="text-sm">
                          {session.exercises.length > 0
                            ? `${session.exercises.length} exercise${session.exercises.length !== 1 ? 's' : ''}`
                            : isPlanned
                              ? `${session.planned_exercises!.length} planned`
                              : 'No exercises'}
                        </div>
                        {session.session_rpe !== null && (
                          <div className="text-xs text-muted-foreground">
                            RPE {session.session_rpe}
                          </div>
                        )}
                      </div>

                      {/* Quick exercise preview */}
                      <div className="hidden lg:block flex-1 text-right text-sm text-muted-foreground">
                        {previewExercises.slice(0, 3).map((ex, idx) => (
                          <span key={idx}>
                            {ex.name}
                            {ex.kg !== null && ` @ ${displayWeight(ex.kg, unit)}`}
                            {idx < Math.min(previewExercises.length, 3) - 1 && ', '}
                          </span>
                        ))}
                        {previewExercises.length > 3 && (
                          <span className="text-muted-foreground">
                            {' '}+{previewExercises.length - 3} more
                          </span>
                        )}
                      </div>
                    </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Session Drawer */}
      <SessionDrawer
        isOpen={drawerDate !== null}
        onClose={() => { setDrawerDate(null); setDrawerArrayIndex(null) }}
        session={selectedSession}
        sessionIndex={selectedSessionIndex}
        sessionArrayIndex={drawerArrayIndex ?? 0}
      />
    </div>
  )
}
