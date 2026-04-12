import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Edit2, Trash2, X, Save, ExternalLink } from 'lucide-react'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import type { Phase } from '@powerlifting/types'

export default function DesignerPhases() {
  const { program, updatePhases } = useProgramStore()
  const { pushToast } = useUiStore()

  const phases = program?.phases || []

  const [editingPhase, setEditingPhase] = useState<Phase | null>(null)
  const [editingPhaseIndex, setEditingPhaseIndex] = useState<number>(-1)
  const [isNewPhase, setIsNewPhase] = useState(false)
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

  const totalWeeks = useMemo(() => {
    if (!phases.length) return 12
    return Math.max(...phases.map(p => p.end_week))
  }, [phases])

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

    const overlaps = updatedPhases.some((phase, idx) => {
      if (idx === editingPhaseIndex) return false
      return !(phaseData.end_week < phase.start_week || phaseData.start_week > phase.end_week)
    })

    if (overlaps) {
      pushToast({ message: 'Phase weeks overlap another phase', type: 'error' })
      return
    }

    if (editingPhaseIndex >= 0) {
      updatedPhases[editingPhaseIndex] = phaseData
    } else {
      updatedPhases.push(phaseData)
    }

    updatedPhases.sort((a, b) => a.start_week - b.start_week)

    await updatePhases(updatedPhases)
    closePhaseEditor()
  }

  async function deletePhase(name: string) {
    if (!confirm(`Delete phase "${name}"?`)) return
    const updatedPhases = phases.filter(p => p.name !== name)
    await updatePhases(updatedPhases)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link to="/designer" className="text-muted-foreground hover:text-foreground text-sm">Designer</Link>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-2xl font-bold">Phase Design</h1>
        </div>
        <button
          onClick={() => openPhaseEditor()}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm"
        >
          <Plus className="w-4 h-4" />
          Add Phase
        </button>
      </div>

      {phases.length > 0 ? (
        <div className="space-y-3">
          {phases.map((phase, i) => (
            <div key={phase.name} className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium">{phase.name}</h3>
                  <p className="text-sm text-muted-foreground">
                    W{phase.start_week} - W{phase.end_week}
                    {phase.target_rpe_min && phase.target_rpe_max && (
                      <> &middot; RPE {phase.target_rpe_min}-{phase.target_rpe_max}</>
                    )}
                    {phase.days_per_week && <> &middot; {phase.days_per_week}x/week</>}
                  </p>
                  {phase.intent && (
                    <p className="text-sm text-muted-foreground mt-1">{phase.intent}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Link
                    to={`/designer/sessions?week=${phase.start_week}`}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-secondary rounded-md hover:bg-accent transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Sessions
                  </Link>
                  <button
                    onClick={() => openPhaseEditor(phase, i)}
                    className="p-1.5 hover:bg-accent rounded"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deletePhase(phase.name)}
                    className="p-1.5 hover:bg-accent rounded text-destructive"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">No phases defined. Click "Add Phase" to get started.</p>
        </div>
      )}

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
