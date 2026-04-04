import { useState, useEffect } from 'react'
import { Plus, X, Trash2, Edit2, Save, ChevronDown, ChevronUp } from 'lucide-react'
import { clsx } from 'clsx'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import type { SupplementPhase, Supplement } from '@powerlifting/types'

export default function SupplementsPage() {
  const { program, updateSupplementPhases } = useProgramStore()
  const { pushToast } = useUiStore()
  const [phases, setPhases] = useState<SupplementPhase[]>([])
  const [hasChanges, setHasChanges] = useState(false)
  const [expandedPhase, setExpandedPhase] = useState<number | null>(null)
  const [editingPhase, setEditingPhase] = useState<number | null>(null)
  const [editingItem, setEditingItem] = useState<{ phaseIndex: number; itemIndex: number } | null>(null)

  useEffect(() => {
    if (program?.supplement_phases) {
      setPhases(program.supplement_phases)
    }
  }, [program])

  function updatePhase(index: number, updates: Partial<SupplementPhase>) {
    setPhases((prev) => {
      const newPhases = [...prev]
      newPhases[index] = { ...newPhases[index], ...updates }
      return newPhases
    })
    setHasChanges(true)
  }

  function updateItem(phaseIndex: number, itemIndex: number, updates: Partial<Supplement & { notes?: string }>) {
    setPhases((prev) => {
      const newPhases = [...prev]
      const items = [...newPhases[phaseIndex].items]
      items[itemIndex] = { ...items[itemIndex], ...updates }
      newPhases[phaseIndex] = { ...newPhases[phaseIndex], items }
      return newPhases
    })
    setHasChanges(true)
  }

  function addItem(phaseIndex: number) {
    setPhases((prev) => {
      const newPhases = [...prev]
      const items = [...newPhases[phaseIndex].items, { name: '', dose: '' }]
      newPhases[phaseIndex] = { ...newPhases[phaseIndex], items }
      return newPhases
    })
    setHasChanges(true)
  }

  function removeItem(phaseIndex: number, itemIndex: number) {
    setPhases((prev) => {
      const newPhases = [...prev]
      const items = newPhases[phaseIndex].items.filter((_, i) => i !== itemIndex)
      newPhases[phaseIndex] = { ...newPhases[phaseIndex], items }
      return newPhases
    })
    setHasChanges(true)
  }

  function addPhase() {
    const maxPhase = phases.reduce((max, p) => Math.max(max, p.phase), 0)
    setPhases((prev) => [
      ...prev,
      {
        phase: maxPhase + 1,
        phase_name: `Phase ${maxPhase + 1}`,
        notes: '',
        items: [],
      },
    ])
    setHasChanges(true)
  }

  function removePhase(index: number) {
    if (!confirm('Delete this phase?')) return
    setPhases((prev) => prev.filter((_, i) => i !== index))
    setHasChanges(true)
  }

  function updateProtocolKey(phaseIndex: number, key: string, value: string) {
    setPhases((prev) => {
      const newPhases = [...prev]
      const protocol = { ...(newPhases[phaseIndex].peak_week_protocol || {}), [key]: value }
      newPhases[phaseIndex] = { ...newPhases[phaseIndex], peak_week_protocol: protocol }
      return newPhases
    })
    setHasChanges(true)
  }

  function addProtocolKey(phaseIndex: number) {
    const key = prompt('Enter protocol key name:')
    if (!key) return
    updateProtocolKey(phaseIndex, key, '')
  }

  function removeProtocolKey(phaseIndex: number, key: string) {
    setPhases((prev) => {
      const newPhases = [...prev]
      const protocol = { ...(newPhases[phaseIndex].peak_week_protocol || {}) }
      delete protocol[key]
      newPhases[phaseIndex] = { ...newPhases[phaseIndex], peak_week_protocol: protocol }
      return newPhases
    })
    setHasChanges(true)
  }

  async function handleSave() {
    try {
      // Sort phases by phase number
      const sortedPhases = [...phases].sort((a, b) => a.phase - b.phase)
      await updateSupplementPhases(sortedPhases)
      setHasChanges(false)
      pushToast({ message: 'Supplement phases saved', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to save supplement phases', type: 'error' })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Supplements</h1>
          <p className="text-muted-foreground">
            Manage supplement phases and peak week protocols
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
            onClick={addPhase}
            className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md font-medium"
          >
            <Plus className="w-4 h-4" />
            Add Phase
          </button>
        </div>
      </div>

      {/* Phase Cards */}
      <div className="space-y-4">
        {phases
          .sort((a, b) => a.phase - b.phase)
          .map((phase, phaseIndex) => {
            const originalIndex = phases.findIndex((p) => p.phase === phase.phase)
            const isExpanded = expandedPhase === phase.phase

            return (
              <div
                key={phase.phase}
                className="bg-card border border-border rounded-lg overflow-hidden"
              >
                {/* Phase Header */}
                <button
                  onClick={() => setExpandedPhase(isExpanded ? null : phase.phase)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-accent/50"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-muted-foreground">
                      Phase {phase.phase}
                    </span>
                    {editingPhase === phase.phase ? (
                      <input
                        type="text"
                        value={phase.phase_name}
                        onChange={(e) => updatePhase(originalIndex, { phase_name: e.target.value })}
                        onBlur={() => setEditingPhase(null)}
                        onKeyDown={(e) => e.key === 'Enter' && setEditingPhase(null)}
                        className="px-2 py-1 border border-border rounded bg-background"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span
                        className="font-medium"
                        onClick={(e) => {
                          e.stopPropagation()
                          setEditingPhase(phase.phase)
                        }}
                      >
                        {phase.phase_name}
                        <Edit2 className="w-3 h-3 ml-2 inline text-muted-foreground" />
                      </span>
                    )}
                    <span className="text-xs px-2 py-0.5 bg-secondary rounded">
                      {phase.items.length} items
                    </span>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  )}
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-2 border-t border-border space-y-4">
                    {/* Phase Notes */}
                    <div>
                      <label className="text-sm text-muted-foreground">Phase Notes</label>
                      <textarea
                        value={phase.notes}
                        onChange={(e) => updatePhase(originalIndex, { notes: e.target.value })}
                        rows={Math.max(2, (phase.notes || '').split('\n').length)}
                        className="w-full mt-1 px-3 py-2 border border-border rounded-md bg-background resize-none overflow-hidden"
                        placeholder="Notes about this phase..."
                        onInput={(e) => { const t = e.currentTarget; t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px' }}
                        ref={(el) => { if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px' } }}
                      />
                    </div>

                    {/* Supplements Table */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm text-muted-foreground">Supplements</label>
                        <button
                          onClick={() => addItem(originalIndex)}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-secondary rounded hover:bg-secondary/80"
                        >
                          <Plus className="w-3 h-3" />
                          Add Item
                        </button>
                      </div>

                      {phase.items.length > 0 ? (
                        <div className="border border-border rounded-lg overflow-hidden">
                          {/* Mobile: card per row */}
                          <div className="sm:hidden divide-y divide-border">
                            {phase.items.map((item, itemIndex) => (
                              <div key={itemIndex} className="p-3 space-y-2">
                                <div className="flex gap-2">
                                  <div className="flex-1">
                                    <label className="text-xs text-muted-foreground">Name</label>
                                    <input
                                      type="text"
                                      value={item.name}
                                      onChange={(e) =>
                                        updateItem(originalIndex, itemIndex, { name: e.target.value })
                                      }
                                      className="w-full px-2 py-2 border border-border rounded bg-background text-sm"
                                    />
                                  </div>
                                  <div className="flex-1">
                                    <label className="text-xs text-muted-foreground">Dose</label>
                                    <input
                                      type="text"
                                      value={item.dose}
                                      onChange={(e) =>
                                        updateItem(originalIndex, itemIndex, { dose: e.target.value })
                                      }
                                      className="w-full px-2 py-2 border border-border rounded bg-background text-sm"
                                    />
                                  </div>
                                  <div className="flex items-end pb-0.5">
                                    <button
                                      onClick={() => removeItem(originalIndex, itemIndex)}
                                      className="p-2 text-muted-foreground hover:text-destructive"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </button>
                                  </div>
                                </div>
                                <textarea
                                  value={item.notes || ''}
                                  onChange={(e) =>
                                    updateItem(originalIndex, itemIndex, { notes: e.target.value })
                                  }
                                  className="w-full px-2 py-2 border border-border rounded bg-background resize-none overflow-hidden text-sm"
                                  placeholder="Notes (optional)"
                                  rows={Math.max(1, (item.notes || '').split('\n').length)}
                                  onInput={(e) => { const t = e.currentTarget; t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px' }}
                                  ref={(el) => { if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px' } }}
                                />
                              </div>
                            ))}
                          </div>

                          {/* Desktop: table */}
                          <table className="hidden sm:table w-full text-sm">
                            <thead>
                              <tr className="bg-muted/50">
                                <th className="text-left px-3 py-2 font-medium w-2/5">Name</th>
                                <th className="text-left px-3 py-2 font-medium w-1/5">Dose</th>
                                <th className="text-left px-3 py-2 font-medium">Notes</th>
                                <th className="w-10"></th>
                              </tr>
                            </thead>
                            <tbody>
                              {phase.items.map((item, itemIndex) => (
                                <tr key={itemIndex} className="border-t border-border">
                                  <td className="px-3 py-2">
                                    <input
                                      type="text"
                                      value={item.name}
                                      onChange={(e) =>
                                        updateItem(originalIndex, itemIndex, { name: e.target.value })
                                      }
                                      className="w-full px-2 py-1 border border-border rounded bg-background"
                                    />
                                  </td>
                                  <td className="px-3 py-2">
                                    <input
                                      type="text"
                                      value={item.dose}
                                      onChange={(e) =>
                                        updateItem(originalIndex, itemIndex, { dose: e.target.value })
                                      }
                                      className="w-full px-2 py-1 border border-border rounded bg-background"
                                    />
                                  </td>
                                  <td className="px-3 py-2">
                                    <textarea
                                      value={item.notes || ''}
                                      onChange={(e) =>
                                        updateItem(originalIndex, itemIndex, { notes: e.target.value })
                                      }
                                      className="w-full px-2 py-1 border border-border rounded bg-background resize-none overflow-hidden"
                                      placeholder="Optional"
                                      rows={Math.max(2, (item.notes || '').split('\n').length)}
                                      onInput={(e) => { const t = e.currentTarget; t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px' }}
                                      ref={(el) => { if (el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px' } }}
                                    />
                                  </td>
                                  <td className="px-3 py-2">
                                    <button
                                      onClick={() => removeItem(originalIndex, itemIndex)}
                                      className="p-1 text-muted-foreground hover:text-destructive"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground py-4 text-center">
                          No supplements in this phase
                        </p>
                      )}
                    </div>

                    {/* Peak Week Protocol */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm text-muted-foreground">Peak Week Protocol</label>
                        <button
                          onClick={() => addProtocolKey(originalIndex)}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-secondary rounded hover:bg-secondary/80"
                        >
                          <Plus className="w-3 h-3" />
                          Add Field
                        </button>
                      </div>

                      {phase.peak_week_protocol && Object.keys(phase.peak_week_protocol).length > 0 ? (
                        <div className="space-y-2">
                          {Object.entries(phase.peak_week_protocol).map(([key, value]) => (
                            <div key={key} className="flex items-center gap-2">
                              <span className="text-sm text-muted-foreground w-32">{key}:</span>
                              <input
                                type="text"
                                value={value}
                                onChange={(e) => updateProtocolKey(originalIndex, key, e.target.value)}
                                className="flex-1 px-2 py-1 border border-border rounded bg-background"
                              />
                              <button
                                onClick={() => removeProtocolKey(originalIndex, key)}
                                className="p-1 text-muted-foreground hover:text-destructive"
                              >
                                <X className="w-4 h-4" />
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground py-2">
                          No peak week protocol defined
                        </p>
                      )}
                    </div>

                    {/* Delete Phase */}
                    <div className="flex justify-end pt-2">
                      <button
                        onClick={() => removePhase(originalIndex)}
                        className="flex items-center gap-1 px-3 py-1 text-sm bg-destructive/10 text-destructive rounded-md hover:bg-destructive/20"
                      >
                        <Trash2 className="w-3 h-3" />
                        Delete Phase
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
      </div>

      {phases.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No supplement phases defined. Click "Add Phase" to get started.
        </div>
      )}
    </div>
  )
}
