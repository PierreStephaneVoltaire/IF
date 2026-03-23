import { useState, useEffect } from 'react'
import { Plus, X, Trash2, Save, Edit2, ChevronDown, ChevronUp, Trophy, Target, CheckCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import { calculateDots } from '@/utils/dots'
import type { Competition, LiftResults } from '@powerlifting/types'

const STATUS_COLORS = {
  completed: 'bg-green-500/20 text-green-600 border-green-500/30',
  confirmed: 'bg-blue-500/20 text-blue-600 border-blue-500/30',
  optional: 'bg-yellow-500/20 text-yellow-600 border-yellow-500/30',
  skipped: 'bg-gray-500/20 text-gray-600 border-gray-500/30',
}

const STATUS_LABELS = {
  completed: 'Completed',
  confirmed: 'Confirmed',
  optional: 'Optional',
  skipped: 'Skipped',
}

export default function CompetitionsPage() {
  const { program, updateCompetitions, migrateLastComp, completeCompetition } = useProgramStore()
  const { pushToast } = useUiStore()
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [hasChanges, setHasChanges] = useState(false)
  const [expandedDate, setExpandedDate] = useState<string | null>(null)
  const [showCompleteModal, setShowCompleteModal] = useState<string | null>(null)
  const [completeForm, setCompleteForm] = useState({
    squat_kg: 0,
    bench_kg: 0,
    deadlift_kg: 0,
    body_weight_kg: 0,
  })

  useEffect(() => {
    if (program?.competitions) {
      // Sort by date ascending (oldest first)
      const sorted = [...program.competitions].sort((a, b) => a.date.localeCompare(b.date))
      setCompetitions(sorted)
    }
  }, [program])

  useEffect(() => {
    // Run migration on first load if needed
    async function checkMigration() {
      const hasCompletedComp = competitions.some((c) => c.status === 'completed')
      if (!hasCompletedComp && program?.meta?.last_comp) {
        try {
          await migrateLastComp()
          pushToast({ message: 'Migrated past competition data', type: 'success' })
        } catch (err) {
          console.error('Migration failed:', err)
        }
      }
    }
    checkMigration()
  }, [])

  function updateComp(date: string, updates: Partial<Competition>) {
    setCompetitions((prev) =>
      prev.map((c) => (c.date === date ? { ...c, ...updates } : c))
    )
    setHasChanges(true)
  }

  function addCompetition() {
    const today = new Date().toISOString().split('T')[0]
    const newComp: Competition = {
      name: 'New Competition',
      date: today,
      federation: '',
      status: 'optional',
      weight_class_kg: 75,
      targets: {
        squat_kg: 0,
        bench_kg: 0,
        deadlift_kg: 0,
        total_kg: 0,
      },
      notes: '',
    }
    setCompetitions((prev) => [...prev, newComp])
    setHasChanges(true)
    setExpandedDate(today)
  }

  function removeCompetition(date: string) {
    if (!confirm('Delete this competition?')) return
    setCompetitions((prev) => prev.filter((c) => c.date !== date))
    setHasChanges(true)
  }

  async function handleSave() {
    try {
      const sorted = [...competitions].sort((a, b) => a.date.localeCompare(b.date))
      await updateCompetitions(sorted)
      setHasChanges(false)
      pushToast({ message: 'Competitions saved', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to save competitions', type: 'error' })
    }
  }

  async function handleMarkComplete(date: string) {
    try {
      const results: LiftResults = {
        squat_kg: completeForm.squat_kg,
        bench_kg: completeForm.bench_kg,
        deadlift_kg: completeForm.deadlift_kg,
        total_kg: completeForm.squat_kg + completeForm.bench_kg + completeForm.deadlift_kg,
      }
      await completeCompetition(date, results, completeForm.body_weight_kg)
      setShowCompleteModal(null)
      pushToast({ message: 'Competition marked as completed', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to mark competition as completed', type: 'error' })
    }
  }

  function openCompleteModal(comp: Competition) {
    setCompleteForm({
      squat_kg: comp.targets?.squat_kg || 0,
      bench_kg: comp.targets?.bench_kg || 0,
      deadlift_kg: comp.targets?.deadlift_kg || 0,
      body_weight_kg: comp.body_weight_kg || comp.weight_class_kg,
    })
    setShowCompleteModal(comp.date)
  }

  function calculateDotsScore(comp: Competition): { dots: number; label: string } | null {
    const total = comp.status === 'completed'
      ? comp.results?.total_kg
      : comp.targets?.total_kg

    if (!total) return null

    // Use body_weight_kg if available, otherwise use weight_class_kg
    const bodyweight = comp.body_weight_kg || comp.weight_class_kg
    const dots = calculateDots(total, bodyweight, 'male')

    return {
      dots,
      label: comp.status === 'completed' ? 'Actual' : 'Projected',
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Competitions</h1>
          <p className="text-muted-foreground">
            Track upcoming and past competitions with DOTS scores
          </p>
        </div>
        <div className="flex gap-2">
          {hasChanges && (
            <button
              onClick={handleSave}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium"
            >
              <Save className="w-4 h-4" />
              Save
            </button>
          )}
          <button
            onClick={addCompetition}
            className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md font-medium"
          >
            <Plus className="w-4 h-4" />
            Add Competition
          </button>
        </div>
      </div>

      {/* Competition Cards */}
      <div className="space-y-4">
        {competitions
          .sort((a, b) => a.date.localeCompare(b.date))
          .map((comp) => {
            const isExpanded = expandedDate === comp.date
            const dotsResult = calculateDotsScore(comp)

            return (
              <div
                key={comp.date}
                className="bg-card border border-border rounded-lg overflow-hidden"
              >
                {/* Competition Header */}
                <button
                  onClick={() => setExpandedDate(isExpanded ? null : comp.date)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-accent/50"
                >
                  <div className="flex items-center gap-3">
                    <Trophy className={clsx(
                      'w-5 h-5',
                      comp.status === 'completed' ? 'text-green-500' :
                      comp.status === 'confirmed' ? 'text-blue-500' :
                      'text-yellow-500'
                    )} />
                    <div className="text-left">
                      <div className="font-medium">{comp.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(comp.date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                        {' • '}
                        {comp.federation || 'No federation'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={clsx(
                        'text-xs px-2 py-0.5 rounded border',
                        STATUS_COLORS[comp.status]
                      )}
                    >
                      {STATUS_LABELS[comp.status]}
                    </span>
                    {dotsResult && (
                      <span className="text-sm font-mono">
                        {dotsResult.label}: {dotsResult.dots.toFixed(1)}
                      </span>
                    )}
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-muted-foreground" />
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-2 border-t border-border space-y-4">
                    {/* Basic Info */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <label className="text-xs text-muted-foreground">Name</label>
                        <input
                          type="text"
                          value={comp.name}
                          onChange={(e) => updateComp(comp.date, { name: e.target.value })}
                          className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Date</label>
                        <input
                          type="date"
                          value={comp.date}
                          onChange={(e) => {
                            const newDate = e.target.value
                            if (competitions.some((c) => c.date === newDate && c.date !== comp.date)) {
                              pushToast({ message: 'A competition on this date already exists', type: 'error' })
                              return
                            }
                            updateComp(comp.date, { date: newDate })
                            setExpandedDate(newDate)
                          }}
                          className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Federation</label>
                        <input
                          type="text"
                          value={comp.federation}
                          onChange={(e) => updateComp(comp.date, { federation: e.target.value })}
                          className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Status</label>
                        <select
                          value={comp.status}
                          onChange={(e) => updateComp(comp.date, { status: e.target.value as Competition['status'] })}
                          className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                        >
                          <option value="optional">Optional</option>
                          <option value="confirmed">Confirmed</option>
                          <option value="completed">Completed</option>
                          <option value="skipped">Skipped</option>
                        </select>
                      </div>
                    </div>

                    {/* Weight & Location */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div>
                        <label className="text-xs text-muted-foreground">Weight Class (kg)</label>
                        <input
                          type="number"
                          value={comp.weight_class_kg}
                          onChange={(e) => updateComp(comp.date, { weight_class_kg: parseFloat(e.target.value) || 0 })}
                          className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                        />
                      </div>
                      {comp.status === 'completed' && (
                        <div>
                          <label className="text-xs text-muted-foreground">Body Weight (kg)</label>
                          <input
                            type="number"
                            step="0.1"
                            value={comp.body_weight_kg || ''}
                            onChange={(e) => updateComp(comp.date, { body_weight_kg: parseFloat(e.target.value) || undefined })}
                            className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                          />
                        </div>
                      )}
                      <div>
                        <label className="text-xs text-muted-foreground">Location</label>
                        <input
                          type="text"
                          value={comp.location || ''}
                          onChange={(e) => updateComp(comp.date, { location: e.target.value })}
                          className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                        />
                      </div>
                    </div>

                    {/* Lifts (Targets or Results) */}
                    <div>
                      <label className="text-xs text-muted-foreground">
                        {comp.status === 'completed' ? 'Results (kg)' : 'Targets (kg)'}
                      </label>
                      <div className="grid grid-cols-4 gap-4 mt-1">
                        {['squat_kg', 'bench_kg', 'deadlift_kg', 'total_kg'].map((lift) => (
                          <div key={lift}>
                            <label className="text-xs text-muted-foreground capitalize">
                              {lift.replace('_kg', '')}
                            </label>
                            <input
                              type="number"
                              value={
                                comp.status === 'completed'
                                  ? comp.results?.[lift as keyof LiftResults] || ''
                                  : comp.targets?.[lift as keyof LiftResults] || ''
                              }
                              onChange={(e) => {
                                const value = parseFloat(e.target.value) || 0
                                const field = comp.status === 'completed' ? 'results' : 'targets'
                                const currentField = comp[field] || {
                                  squat_kg: 0,
                                  bench_kg: 0,
                                  deadlift_kg: 0,
                                  total_kg: 0,
                                }
                                // Calculate new total using the updated value
                                const newLifts = {
                                  squat_kg: currentField.squat_kg || 0,
                                  bench_kg: currentField.bench_kg || 0,
                                  deadlift_kg: currentField.deadlift_kg || 0,
                                  [lift]: value,
                                }
                                const newTotal = newLifts.squat_kg + newLifts.bench_kg + newLifts.deadlift_kg
                                updateComp(comp.date, {
                                  [field]: {
                                    ...currentField,
                                    [lift]: value,
                                    total_kg: newTotal,
                                  },
                                })
                              }}
                              className="w-full px-2 py-1 border border-border rounded bg-background"
                              disabled={lift === 'total_kg'}
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* DOTS Score */}
                    {dotsResult && (
                      <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg">
                        <Target className="w-4 h-4 text-primary" />
                        <span className="text-sm">
                          <span className="text-muted-foreground">{dotsResult.label} DOTS:</span>{' '}
                          <span className="font-mono font-bold">{dotsResult.dots.toFixed(2)}</span>
                        </span>
                      </div>
                    )}

                    {/* Notes */}
                    <div>
                      <label className="text-xs text-muted-foreground">Notes</label>
                      <textarea
                        value={comp.notes || ''}
                        onChange={(e) => updateComp(comp.date, { notes: e.target.value })}
                        rows={3}
                        className="w-full mt-1 px-3 py-2 border border-border rounded-md bg-background resize-none"
                        placeholder="Competition notes..."
                      />
                    </div>

                    {/* Actions */}
                    <div className="flex justify-between pt-2">
                      {/* Mark Complete Button */}
                      {comp.status !== 'completed' && new Date(comp.date) < new Date() && (
                        <button
                          onClick={() => openCompleteModal(comp)}
                          className="flex items-center gap-1 px-3 py-1 text-sm bg-green-500/10 text-green-600 rounded-md hover:bg-green-500/20"
                        >
                          <CheckCircle className="w-3 h-3" />
                          Mark as Completed
                        </button>
                      )}
                      <div className="flex-1" />
                      <button
                        onClick={() => removeCompetition(comp.date)}
                        className="flex items-center gap-1 px-3 py-1 text-sm bg-destructive/10 text-destructive rounded-md hover:bg-destructive/20"
                      >
                        <Trash2 className="w-3 h-3" />
                        Delete
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
      </div>

      {/* Complete Competition Modal */}
      {showCompleteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg shadow-xl max-w-md w-full mx-4 p-6 space-y-4">
            <h3 className="text-lg font-semibold">Mark Competition as Completed</h3>
            <p className="text-sm text-muted-foreground">
              Enter the actual results from the competition.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground">Squat (kg)</label>
                <input
                  type="number"
                  value={completeForm.squat_kg}
                  onChange={(e) => setCompleteForm((p) => ({ ...p, squat_kg: parseFloat(e.target.value) || 0 }))}
                  className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Bench (kg)</label>
                <input
                  type="number"
                  value={completeForm.bench_kg}
                  onChange={(e) => setCompleteForm((p) => ({ ...p, bench_kg: parseFloat(e.target.value) || 0 }))}
                  className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Deadlift (kg)</label>
                <input
                  type="number"
                  value={completeForm.deadlift_kg}
                  onChange={(e) => setCompleteForm((p) => ({ ...p, deadlift_kg: parseFloat(e.target.value) || 0 }))}
                  className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Body Weight at Weigh-in (kg)</label>
                <input
                  type="number"
                  step="0.1"
                  value={completeForm.body_weight_kg}
                  onChange={(e) => setCompleteForm((p) => ({ ...p, body_weight_kg: parseFloat(e.target.value) || 0 }))}
                  className="w-full mt-1 px-2 py-1 border border-border rounded bg-background"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowCompleteModal(null)}
                className="px-4 py-2 bg-secondary rounded-md"
              >
                Cancel
              </button>
              <button
                onClick={() => handleMarkComplete(showCompleteModal)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium"
              >
                Complete
              </button>
            </div>
          </div>
        </div>
      )}

      {competitions.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No competitions yet. Click "Add Competition" to get started.
        </div>
      )}
    </div>
  )
}
