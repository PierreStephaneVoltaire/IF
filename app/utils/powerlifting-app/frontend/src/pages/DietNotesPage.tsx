import { useState, useEffect } from 'react'
import { Plus, X, Trash2, Save, Calendar } from 'lucide-react'
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
                    // Check for duplicate dates
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

            {/* Notes Textarea */}
            <textarea
              value={note.notes}
              onChange={(e) => updateNote(note.date, { notes: e.target.value })}
              rows={4}
              className="w-full px-3 py-2 border border-border rounded-md bg-background resize-none"
              placeholder="Enter diet notes, meals, observations..."
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
