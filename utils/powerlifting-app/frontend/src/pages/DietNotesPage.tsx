import { useState, useEffect } from 'react'
import { Plus, Trash2, Save, Calendar, Droplets, Flame, CheckCircle, XCircle } from 'lucide-react'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import type { DietNote } from '@powerlifting/types'

export default function DietNotesPage() {
  const { program, updateDietNotes } = useProgramStore()
  const { pushToast } = useUiStore()
  const [notes, setNotes] = useState<DietNote[]>([])
  const [hasChanges, setHasChanges] = useState(false)
  const [editingDate, setEditingDate] = useState<string | null>(null)

  useEffect(() => {
    if (program?.diet_notes) {
      // Sort by date descending (newest first)
      const sorted = [...program.diet_notes].sort((a, b) => b.date.localeCompare(a.date))
      setNotes(sorted)
    }
  }, [program])

  function updateNote(date: string, updates: Partial<DietNote>) {
    setNotes((prev) =>
      prev.map((n) => (n.date === date ? { ...n, ...updates } : n))
    )
    setHasChanges(true)
  }

  function addNote() {
    const today = new Date().toISOString().split('T')[0]
    // Check if today already has a note
    if (notes.some((n) => n.date === today)) {
      pushToast({ message: 'A note for today already exists', type: 'error' })
      return
    }
    setNotes((prev) => [{ date: today, notes: '' }, ...prev])
    setHasChanges(true)
    setEditingDate(today)
  }

  function removeNote(date: string) {
    if (!confirm('Delete this note?')) return
    setNotes((prev) => prev.filter((n) => n.date !== date))
    setHasChanges(true)
  }

  async function handleSave() {
    try {
      // Sort by date before saving
      const sorted = [...notes].sort((a, b) => b.date.localeCompare(a.date))
      await updateDietNotes(sorted)
      setHasChanges(false)
      pushToast({ message: 'Diet notes saved', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to save diet notes', type: 'error' })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Diet Notes</h1>
          <p className="text-muted-foreground">
            Track daily nutrition and diet observations
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
            onClick={addNote}
            className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md font-medium"
          >
            <Plus className="w-4 h-4" />
            Add Entry
          </button>
        </div>
      </div>

      {/* Notes List */}
      <div className="space-y-4">
        {notes.map((note) => (
          <div
            key={note.date}
            className="bg-card border border-border rounded-lg p-4 space-y-3"
          >
            {/* Date Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-muted-foreground" />
                <input
                  type="date"
                  value={note.date}
                  onChange={(e) => {
                    const newDate = e.target.value
                    if (notes.some((n) => n.date === newDate && n.date !== note.date)) {
                      pushToast({ message: 'A note for this date already exists', type: 'error' })
                      return
                    }
                    updateNote(note.date, { date: newDate })
                  }}
                  className="px-2 py-1 border border-border rounded bg-background text-sm"
                />
              </div>
              <button
                onClick={() => removeNote(note.date)}
                className="p-1 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            {/* Nutrition Fields */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Avg Daily Calories */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground flex items-center gap-1">
                  <Flame className="w-3 h-3" />
                  Avg Daily Calories
                </label>
                <input
                  type="number"
                  value={note.avg_daily_calories ?? ''}
                  onChange={(e) => updateNote(note.date, {
                    avg_daily_calories: e.target.value ? Number(e.target.value) : undefined,
                  })}
                  className="w-full px-2 py-1.5 border border-border rounded bg-background text-sm"
                  placeholder="e.g. 2500"
                />
              </div>

              {/* Water Intake */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground flex items-center gap-1">
                  <Droplets className="w-3 h-3" />
                  Water Intake
                </label>
                <div className="flex gap-1">
                  <input
                    type="number"
                    step="0.1"
                    value={note.water_intake ?? ''}
                    onChange={(e) => updateNote(note.date, {
                      water_intake: e.target.value ? Number(e.target.value) : undefined,
                    })}
                    className="flex-1 px-2 py-1.5 border border-border rounded bg-background text-sm"
                    placeholder="e.g. 2.5"
                  />
                  <select
                    value={note.water_unit || 'litres'}
                    onChange={(e) => updateNote(note.date, {
                      water_unit: e.target.value as 'litres' | 'cups',
                    })}
                    className="px-2 py-1.5 border border-border rounded bg-background text-sm"
                  >
                    <option value="litres">L</option>
                    <option value="cups">cups</option>
                  </select>
                </div>
              </div>

              {/* Consistency */}
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Consistency</label>
                <div className="flex gap-1">
                  <button
                    onClick={() => updateNote(note.date, { consistent: true })}
                    className={`flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded text-xs font-medium border ${
                      note.consistent
                        ? 'bg-green-100 text-green-700 border-green-300 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800'
                        : 'bg-background text-muted-foreground border-border'
                    }`}
                  >
                    <CheckCircle className="w-3 h-3" />
                    Consistent
                  </button>
                  <button
                    onClick={() => updateNote(note.date, { consistent: false })}
                    className={`flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded text-xs font-medium border ${
                      note.consistent === false
                        ? 'bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800'
                        : 'bg-background text-muted-foreground border-border'
                    }`}
                  >
                    <XCircle className="w-3 h-3" />
                    On & Off
                  </button>
                </div>
              </div>
            </div>

            {/* Notes Textarea */}
            <textarea
              value={note.notes}
              onChange={(e) => updateNote(note.date, { notes: e.target.value })}
              rows={3}
              className="w-full px-3 py-2 border border-border rounded-md bg-background resize-none text-sm"
              placeholder="Diet notes, meals, observations..."
            />
          </div>
        ))}
      </div>

      {notes.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          No diet notes yet. Click "Add Entry" to get started.
        </div>
      )}
    </div>
  )
}
