import { Fragment, useState, useEffect } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { formatDateLong, getDayOfWeek } from '@/utils/dates'
import { displayWeight, toDisplayUnit, fromDisplayUnit } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
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
}

export default function SessionDrawer({
  isOpen,
  onClose,
  session,
  sessionIndex,
}: SessionDrawerProps) {
  const { program, updateSession, saveSession, rescheduleSession, deleteSession } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()

  const [localSession, setLocalSession] = useState<Session | null>(null)
  const [originalDate, setOriginalDate] = useState<string>('')
  const [hasChanges, setHasChanges] = useState(false)
  const [showVideoUpload, setShowVideoUpload] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

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
        await rescheduleSession(originalDate, localSession.date, newDay)
      }

      // Update session content
      updateSession(localSession.date, localSession)
      await saveSession(localSession.date)

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
      await deleteSession(originalDate)
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
                      {localSession.exercises.map((exercise, index) => (
                        <div
                          key={index}
                          className="bg-card border border-border rounded-lg p-3 space-y-2"
                        >
                          <div className="flex items-start gap-2">
                            <GripVertical className="w-4 h-4 text-muted-foreground mt-2 cursor-move" />
                            <div className="flex-1 grid grid-cols-3 sm:grid-cols-4 gap-2">
                              <div className="col-span-3 sm:col-span-4 flex items-center gap-1">
                                <input
                                  type="text"
                                  value={exercise.name}
                                  onChange={(e) => updateExercise(index, 'name', e.target.value)}
                                  placeholder="Exercise name"
                                  className="flex-1 px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm"
                                />
                                <button
                                  onClick={() => removeExercise(index)}
                                  className="sm:hidden p-2 text-destructive hover:bg-destructive/10 rounded"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                              <div>
                                <label className="text-xs text-muted-foreground">Sets</label>
                                <input
                                  type="number"
                                  value={exercise.sets || ''}
                                  onChange={(e) => updateExercise(index, 'sets', Number(e.target.value) || 0)}
                                  className="w-full px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm"
                                />
                              </div>
                              <div>
                                <label className="text-xs text-muted-foreground">Reps</label>
                                <input
                                  type="number"
                                  value={exercise.reps || ''}
                                  onChange={(e) => updateExercise(index, 'reps', Number(e.target.value) || 0)}
                                  className="w-full px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm"
                                />
                              </div>
                              <div>
                                <label className="text-xs text-muted-foreground">{unit}</label>
                                <input
                                  type="number"
                                  step="0.25"
                                  value={exercise.kg ? toDisplayUnit(exercise.kg, unit) : ''}
                                  onChange={(e) =>
                                    updateExercise(
                                      index,
                                      'kg',
                                      e.target.value ? fromDisplayUnit(Number(e.target.value), unit) : null
                                    )
                                  }
                                  className="w-full px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm"
                                />
                              </div>
                              <div className="hidden sm:flex items-end">
                                <button
                                  onClick={() => removeExercise(index)}
                                  className="p-2 sm:p-1 text-destructive hover:bg-destructive/10 rounded"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                              <input
                                type="text"
                                value={exercise.notes || ''}
                                onChange={(e) => updateExercise(index, 'notes', e.target.value)}
                                placeholder="Notes"
                                className="w-full px-2 py-2 sm:py-1 border border-border rounded bg-background text-sm col-span-3 sm:col-span-4"
                              />
                            </div>
                          </div>
                        </div>
                      ))}

                      <button
                        onClick={addExercise}
                        className="w-full py-2 border border-dashed border-border rounded-lg text-sm text-muted-foreground hover:border-primary hover:text-primary transition-colors"
                      >
                        <Plus className="w-4 h-4 inline mr-1" />
                        Add Exercise
                      </button>

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
