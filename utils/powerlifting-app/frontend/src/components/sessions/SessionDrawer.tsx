import { Fragment, useState, useEffect, useMemo } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { formatDateLong, getDayOfWeek } from '@/utils/dates'
import { displayWeight, toDisplayUnit, fromDisplayUnit } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import { fetchGlossary } from '@/api/client'
import { clsx } from 'clsx'
import { X, Check, Save, RotateCcw, Plus, GripVertical, Trash2, Calendar, Film, Loader2 } from 'lucide-react'
import type { Session, Exercise, SessionVideo } from '@powerlifting/types'
import VideoGrid from './VideoGrid'
import VideoUploadModal from './VideoUploadModal'

interface SessionDrawerProps {
  isOpen: boolean
  onClose: () => void
  session: Session | null
  sessionIndex: number
  sessionArrayIndex: number
}

export default function SessionDrawer({
  isOpen,
  onClose,
  session,
  sessionIndex,
  sessionArrayIndex,
}: SessionDrawerProps) {
  const { program, updateSession, saveSession, rescheduleSession, deleteSession } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()

  const [localSession, setLocalSession] = useState<Session | null>(null)
  const [originalDate, setOriginalDate] = useState<string>('')
  const [hasChanges, setHasChanges] = useState(false)
  const [showVideoUpload, setShowVideoUpload] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [glossaryNames, setGlossaryNames] = useState<string[]>([])

  useEffect(() => {
    fetchGlossary()
      .then((exercises) => setGlossaryNames(exercises.map((e) => e.name).sort()))
      .catch(() => {})
  }, [])

  // Initialize local state when session changes
  useEffect(() => {
    if (session) {
      setLocalSession(JSON.parse(JSON.stringify(session)))
      setOriginalDate(session.date)
      setHasChanges(false)
    }
  }, [session])

  if (!session || !localSession || !program) return null

  const handleSave = async () => {
    try {
      // Check if date changed
      if (localSession.date !== originalDate) {
        // First reschedule, then save content
        const newDay = getDayOfWeek(localSession.date)
        await rescheduleSession(originalDate, sessionArrayIndex, localSession.date, newDay)
      }

      // Update session content
      updateSession(localSession.date, sessionArrayIndex, localSession)
      await saveSession(localSession.date, sessionArrayIndex)

      setHasChanges(false)
      pushToast({ message: 'Session saved successfully', type: 'success' })
      onClose()
    } catch (err) {
      console.error(err)
      pushToast({ message: 'Failed to save session', type: 'error' })
    }
  }

  const handleDiscard = () => {
    setLocalSession(JSON.parse(JSON.stringify(session)))
    setHasChanges(false)
  }

  const handleCloseWithCheck = () => {
    if (hasChanges) {
      if (confirm('You have unsaved changes. Discard them?')) {
        handleDiscard()
        onClose()
      }
    } else {
      onClose()
    }
  }

  const updateExercise = (index: number, field: keyof Exercise, value: unknown) => {
    setLocalSession((prev) => {
      if (!prev) return prev
      const exercises = [...prev.exercises]
      exercises[index] = { ...exercises[index], [field]: value }
      return { ...prev, exercises }
    })
    setHasChanges(true)
  }

  const addExercise = () => {
    setLocalSession((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        exercises: [
          ...prev.exercises,
          { name: '', sets: 3, reps: 5, kg: null, notes: '' },
        ],
      }
    })
    setHasChanges(true)
  }

  const removeExercise = (index: number) => {
    setLocalSession((prev) => {
      if (!prev) return prev
      const exercises = prev.exercises.filter((_, i) => i !== index)
      return { ...prev, exercises }
    })
    setHasChanges(true)
  }

  const updateDate = (newDate: string) => {
    if (newDate && newDate !== localSession.date) {
      const newDay = getDayOfWeek(newDate)
      setLocalSession((prev) => prev ? { ...prev, date: newDate, day: newDay } : prev)
      setHasChanges(true)
    }
  }

  const toggleComplete = () => {
    setLocalSession((prev) => prev ? { ...prev, completed: !prev.completed } : prev)
    setHasChanges(true)
  }

  const updateRpe = (rpe: number | null) => {
    setLocalSession((prev) => prev ? { ...prev, session_rpe: rpe } : prev)
    setHasChanges(true)
  }

  const updateBodyWeight = (kg: number | null) => {
    setLocalSession((prev) => prev ? { ...prev, body_weight_kg: kg } : prev)
    setHasChanges(true)
  }

  const updateNotes = (notes: string) => {
    setLocalSession((prev) => prev ? { ...prev, session_notes: notes } : prev)
    setHasChanges(true)
  }

  const handleDelete = async () => {
    if (!confirm('Delete this entire session? This cannot be undone.')) return
    setIsDeleting(true)
    try {
      await deleteSession(originalDate, sessionArrayIndex)
      pushToast({ message: 'Session deleted', type: 'success' })
      onClose()
    } catch (err) {
      console.error(err)
      pushToast({ message: 'Failed to delete session', type: 'error' })
    } finally {
      setIsDeleting(false)
    }
  }

  const phaseColorValue = phaseColor(session.phase, program.phases)

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleCloseWithCheck}>
        <Transition.Child
          as={Fragment}
          enter="ease-in-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in-out duration-300"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/25" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-0 sm:pl-10">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-in-out duration-300"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in-out duration-300"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel className="pointer-events-auto w-screen max-w-full sm:max-w-md">
                  <div className="flex h-full flex-col bg-background shadow-xl">
                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: phaseColorValue }}
                        />
                        <div>
                          <p className="font-medium">{localSession.week}</p>
                          <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4 text-muted-foreground" />
                            <input
                              type="date"
                              value={localSession.date}
                              onChange={(e) => updateDate(e.target.value)}
                              className="text-sm bg-secondary px-2 py-1 rounded border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                            />
                            <span className="text-xs text-muted-foreground">{localSession.day}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={toggleComplete}
                          className={clsx(
                            'px-3 py-1 rounded-md text-sm font-medium transition-colors',
                            localSession.completed
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-secondary text-secondary-foreground'
                          )}
                        >
                          {localSession.completed ? (
                            <Check className="w-4 h-4 inline mr-1" />
                          ) : null}
                          {localSession.completed ? 'Done' : 'Mark Done'}
                        </button>
                        <button
                          onClick={handleCloseWithCheck}
                          className="p-2 rounded-md hover:bg-accent"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>
                    </div>

                    {/* Exercises */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-3">
                      {(() => {
                        const groups: Array<{ name: string; entries: Array<{ exercise: Exercise; originalIndex: number }> }> = []
                        for (let i = 0; i < localSession.exercises.length; i++) {
                          const exercise = localSession.exercises[i]
                          const existing = groups.find(g => g.name === exercise.name)
                          if (existing) {
                            existing.entries.push({ exercise, originalIndex: i })
                          } else {
                            groups.push({ name: exercise.name, entries: [{ exercise, originalIndex: i }] })
                          }
                        }
                        return groups.map((group, groupIdx) => (
                          <div key={group.name || `ungrouped-${groupIdx}`} className="bg-card border border-border rounded-lg p-3">
                            <div className="flex items-center gap-2 mb-2">
                              <GripVertical className="w-4 h-4 text-muted-foreground cursor-move" />
                              <input
                                type="text"
                                value={group.name}
                                onChange={(e) => {
                                  const newName = e.target.value
                                  setLocalSession((prev) => {
                                    if (!prev) return prev
                                    const exercises = prev.exercises.map((ex, i) =>
                                      group.entries.some(entry => entry.originalIndex === i)
                                        ? { ...ex, name: newName }
                                        : ex
                                    )
                                    return { ...prev, exercises }
                                  })
                                  setHasChanges(true)
                                }}
                                placeholder="Exercise name"
                                list="exercise-glossary"
                                className="flex-1 px-2 py-1 border border-border rounded bg-background text-sm font-medium"
                              />
                              {group.entries.length === 1 && (
                                <button onClick={() => removeExercise(group.entries[0].originalIndex)} className="p-1 text-destructive hover:bg-destructive/10 rounded">
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                            {group.entries.length > 1 ? (
                              <table className="w-full text-sm mb-1">
                                <thead>
                                  <tr className="border-b border-border text-xs text-muted-foreground">
                                    <th className="text-left py-1 px-1 w-12">Sets</th>
                                    <th className="text-left py-1 px-1 w-12">Reps</th>
                                    <th className="text-left py-1 px-1 w-16">{unit}</th>
                                    <th className="text-left py-1 px-1">Notes</th>
                                    <th className="w-8" />
                                  </tr>
                                </thead>
                                <tbody>
                                  {group.entries.map((entry) => (
                                    <tr key={entry.originalIndex} className="border-b border-border/50 last:border-b-0">
                                      <td className="py-1 px-1">
                                        <input type="number" value={entry.exercise.sets || ''} onChange={(e) => updateExercise(entry.originalIndex, 'sets', Number(e.target.value) || 0)} className="w-full px-1 py-0.5 border border-border rounded bg-background text-sm" />
                                      </td>
                                      <td className="py-1 px-1">
                                        <input type="number" value={entry.exercise.reps || ''} onChange={(e) => updateExercise(entry.originalIndex, 'reps', Number(e.target.value) || 0)} className="w-full px-1 py-0.5 border border-border rounded bg-background text-sm" />
                                      </td>
                                      <td className="py-1 px-1">
                                        <input type="number" step={0.25} value={entry.exercise.kg ? toDisplayUnit(entry.exercise.kg, unit) : ''} onChange={(e) => updateExercise(entry.originalIndex, 'kg', e.target.value ? fromDisplayUnit(Number(e.target.value), unit) : null)} className="w-full px-1 py-0.5 border border-border rounded bg-background text-sm" />
                                      </td>
                                      <td className="py-1 px-1">
                                        <input type="text" value={entry.exercise.notes || ''} onChange={(e) => updateExercise(entry.originalIndex, 'notes', e.target.value)} placeholder="Notes" className="w-full px-1 py-0.5 border border-border rounded bg-background text-sm" />
                                      </td>
                                      <td className="py-1 px-1">
                                        <button onClick={() => removeExercise(entry.originalIndex)} className="p-0.5 text-destructive hover:bg-destructive/10 rounded">
                                          <Trash2 className="w-3 h-3" />
                                        </button>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            ) : (
                              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                                <div>
                                  <label className="text-xs text-muted-foreground">Sets</label>
                                  <input type="number" value={group.entries[0].exercise.sets || ''} onChange={(e) => updateExercise(group.entries[0].originalIndex, 'sets', Number(e.target.value) || 0)} className="w-full px-2 py-1 border border-border rounded bg-background text-sm" />
                                </div>
                                <div>
                                  <label className="text-xs text-muted-foreground">Reps</label>
                                  <input type="number" value={group.entries[0].exercise.reps || ''} onChange={(e) => updateExercise(group.entries[0].originalIndex, 'reps', Number(e.target.value) || 0)} className="w-full px-2 py-1 border border-border rounded bg-background text-sm" />
                                </div>
                                <div>
                                  <label className="text-xs text-muted-foreground">{unit}</label>
                                  <input type="number" step={0.25} value={group.entries[0].exercise.kg ? toDisplayUnit(group.entries[0].exercise.kg, unit) : ''} onChange={(e) => updateExercise(group.entries[0].originalIndex, 'kg', e.target.value ? fromDisplayUnit(Number(e.target.value), unit) : null)} className="w-full px-2 py-1 border border-border rounded bg-background text-sm" />
                                </div>
                                <div>
                                  <label className="text-xs text-muted-foreground">Notes</label>
                                  <input type="text" value={group.entries[0].exercise.notes || ''} onChange={(e) => updateExercise(group.entries[0].originalIndex, 'notes', e.target.value)} placeholder="Notes" className="w-full px-2 py-1 border border-border rounded bg-background text-sm col-span-3 sm:col-span-1" />
                                </div>
                              </div>
                            )}
                          </div>
                        ))
                      })()}

                      <button
                        onClick={addExercise}
                        className="w-full py-2 border border-dashed border-border rounded-lg text-sm text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                      >
                        <Plus className="w-4 h-4 inline mr-1" />
                        Add Exercise
                      </button>

                      <datalist id="exercise-glossary">
                        {glossaryNames.map((name) => (
                          <option key={name} value={name} />
                        ))}
                      </datalist>

                      {/* Videos Section */}
                      <div className="pt-4 border-t border-border">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-sm font-medium flex items-center gap-2">
                            <Film className="w-4 h-4" />
                            Videos
                            {(session.videos?.length || 0) > 0 && (
                              <span className="text-xs text-muted-foreground">
                                ({session.videos?.length})
                              </span>
                            )}
                          </h3>
                          <button
                            onClick={() => setShowVideoUpload(true)}
                            className="flex items-center gap-1 px-2 py-1 text-xs bg-secondary rounded hover:bg-secondary/80"
                          >
                            <Plus className="w-3 h-3" />
                            Upload
                          </button>
                        </div>

                        {session.videos && session.videos.length > 0 ? (
                          <VideoGrid session={session} />
                        ) : (
                          <p className="text-xs text-muted-foreground text-center py-4">
                            No videos uploaded for this session
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Footer */}
                    <div className="border-t border-border p-4 space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-muted-foreground">Session RPE</label>
                          <input
                            type="number"
                            min={1}
                            max={10}
                            step={0.5}
                            value={localSession.session_rpe || ''}
                            onChange={(e) => updateRpe(Number(e.target.value) || null)}
                            placeholder="1-10"
                            className="w-full px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground">Body Weight ({unit})</label>
                          <input
                            type="number"
                            step="0.1"
                            value={
                              localSession.body_weight_kg
                                ? toDisplayUnit(localSession.body_weight_kg, unit)
                                : ''
                            }
                            onChange={(e) => updateBodyWeight(e.target.value ? fromDisplayUnit(Number(e.target.value), unit) : null)}
                            placeholder={unit}
                            className="w-full px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="text-xs text-muted-foreground">Session Notes</label>
                        <textarea
                          value={localSession.session_notes || ''}
                          onChange={(e) => updateNotes(e.target.value)}
                          placeholder="How did the session feel?"
                          rows={2}
                          className="w-full px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm resize-none"
                        />
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2">
                        <button
                          onClick={handleDelete}
                          disabled={isDeleting}
                          className={clsx(
                            'flex items-center justify-center min-w-[44px] min-h-[44px] py-2 px-3 rounded-md text-sm font-medium transition-colors',
                            'text-destructive hover:bg-destructive/10',
                            isDeleting && 'opacity-50 cursor-not-allowed'
                          )}
                        >
                          {isDeleting ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={handleDiscard}
                          disabled={!hasChanges}
                          className={clsx(
                            'flex-1 py-2 rounded-md text-sm font-medium transition-colors',
                            hasChanges
                              ? 'bg-secondary text-secondary-foreground hover:bg-accent'
                              : 'bg-muted text-muted-foreground cursor-not-allowed'
                          )}
                        >
                          <RotateCcw className="w-4 h-4 inline mr-1" />
                          Discard
                        </button>
                        <button
                          onClick={handleSave}
                          disabled={!hasChanges}
                          className={clsx(
                            'flex-1 py-2 rounded-md text-sm font-medium transition-colors',
                            hasChanges
                              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                            : 'bg-muted text-muted-foreground cursor-not-allowed'
                          )}
                        >
                          <Save className="w-4 h-4 inline mr-1" />
                          Save
                        </button>
                      </div>
                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </div>
      </Dialog>

      {/* Video Upload Modal */}
      <VideoUploadModal
        session={session}
        isOpen={showVideoUpload}
        onClose={() => setShowVideoUpload(false)}
        onUploaded={(video: SessionVideo) => {
          // Reload session to get updated videos
          setLocalSession((prev) => {
            if (!prev) return prev
            return {
              ...prev,
              videos: [...(prev.videos || []), video],
            }
          })
        }}
      />
    </Transition>
  )
}
