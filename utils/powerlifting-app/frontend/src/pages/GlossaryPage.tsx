import { useState, useEffect, useMemo, useCallback } from 'react'
import { Search, Plus, X, ChevronDown, ChevronUp, Trash2, Edit2, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'
import * as Slider from '@radix-ui/react-slider'
import * as api from '@/api/client'
import { useUiStore } from '@/store/uiStore'
import type { GlossaryExercise, MuscleGroup, ExerciseCategory, Equipment, FatigueCategory, FatigueProfile, FatigueProfileSource } from '@powerlifting/types'

interface FatigueSliderProps {
  label: string
  value: number
  onChange: (v: number) => void
}

function FatigueSlider({ label, value, onChange }: FatigueSliderProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono text-xs tabular-nums">{(value / 100).toFixed(2)}</span>
      </div>
      <Slider.Root
        className="relative flex items-center select-none touch-none w-full h-5"
        value={[value]}
        onValueChange={([v]) => onChange(v)}
        min={0}
        max={100}
        step={5}
      >
        <Slider.Track className="bg-secondary relative grow rounded-full h-2">
          <Slider.Range className="absolute bg-primary rounded-full h-full" />
        </Slider.Track>
        <Slider.Thumb className="block w-4 h-4 bg-background border-2 border-primary rounded-full hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary" />
      </Slider.Root>
    </div>
  )
}

const MUSCLE_LABELS: Record<MuscleGroup, string> = {
  quads: 'Quads',
  hamstrings: 'Hamstrings',
  glutes: 'Glutes',
  calves: 'Calves',
  hip_flexors: 'Hip Flexors',
  chest: 'Chest',
  triceps: 'Triceps',
  front_delts: 'Front Delts',
  side_delts: 'Side Delts',
  rear_delts: 'Rear Delts',
  lats: 'Lats',
  traps: 'Traps',
  rhomboids: 'Rhomboids',
  teres_major: 'Teres Major',
  biceps: 'Biceps',
  forearms: 'Forearms',
  erectors: 'Erectors',
  lower_back: 'Lower Back',
  core: 'Core',
  obliques: 'Obliques',
}

const CATEGORY_LABELS: Record<ExerciseCategory, string> = {
  squat: 'Squat',
  bench: 'Bench',
  deadlift: 'Deadlift',
  back: 'Back',
  chest: 'Chest',
  arm: 'Arms',
  legs: 'Legs',
  core: 'Core',
  lower_back: 'Lower Back',
}

const EQUIPMENT_LABELS: Record<Equipment, string> = {
  barbell: 'Barbell',
  dumbbell: 'Dumbbell',
  cable: 'Cable',
  machine: 'Machine',
  bodyweight: 'Bodyweight',
  hex_bar: 'Hex Bar',
  bands: 'Bands',
  kettlebell: 'Kettlebell',
}

const FATIGUE_CATEGORY_OPTIONS: { value: FatigueCategory; label: string }[] = [
  { value: 'primary_axial', label: 'Primary Axial' },
  { value: 'primary_upper', label: 'Primary Upper' },
  { value: 'secondary', label: 'Secondary' },
  { value: 'accessory', label: 'Accessory' },
]

const FATIGUE_LABELS: Record<FatigueCategory, string> = {
  primary_axial: 'Primary Axial',
  primary_upper: 'Primary Upper',
  secondary: 'Secondary',
  accessory: 'Accessory',
}

export default function GlossaryPage() {
  const { pushToast } = useUiStore()
  const [exercises, setExercises] = useState<GlossaryExercise[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState<GlossaryExercise | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)

  // Form state for add/edit
  const [formData, setFormData] = useState<Partial<GlossaryExercise>>({
    name: '',
    category: 'squat',
    fatigue_category: 'accessory',
    primary_muscles: [],
    secondary_muscles: [],
    equipment: 'barbell',
    cues: [],
    notes: '',
  })
  const [cueInput, setCueInput] = useState('')
  const [fatigueProfile, setFatigueProfile] = useState<FatigueProfile | null>(null)
  const [fatigueSource, setFatigueSource] = useState<FatigueProfileSource | null>(null)
  const [fatigueReasoning, setFatigueReasoning] = useState<string | null>(null)
  const [isEstimating, setIsEstimating] = useState(false)

  useEffect(() => {
    loadExercises()
  }, [])

  async function loadExercises() {
    try {
      setIsLoading(true)
      const data = await api.fetchGlossary()
      setExercises(data || [])
    } catch (err) {
      console.error('Failed to load glossary:', err)
      pushToast({ message: 'Failed to load exercises', type: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  async function handleSearch(query: string) {
    setSearchQuery(query)
    if (!query.trim()) {
      loadExercises()
      return
    }
    try {
      const data = await api.searchExercises(query)
      setExercises(data || [])
    } catch (err) {
      console.error('Search failed:', err)
    }
  }

  async function handleSave() {
    if (!formData.name) {
      pushToast({ message: 'Exercise name is required', type: 'error' })
      return
    }

    try {
      const exercise: GlossaryExercise = {
        ...(isEditing || {}),
        name: formData.name || '',
        category: formData.category || 'squat',
        fatigue_category: formData.fatigue_category || 'accessory',
        primary_muscles: formData.primary_muscles || [],
        secondary_muscles: formData.secondary_muscles || [],
        equipment: formData.equipment || 'barbell',
        cues: formData.cues || [],
        notes: formData.notes || '',
        fatigue_profile: fatigueProfile || undefined,
        fatigue_profile_source: fatigueSource || undefined,
        fatigue_profile_reasoning: fatigueReasoning,
      }

      await api.upsertExercise(exercise)
      pushToast({
        message: isEditing ? 'Exercise updated' : 'Exercise added',
        type: 'success'
      })
      setShowAddForm(false)
      setIsEditing(null)
      setFormData({
        name: '',
        category: 'squat',
        fatigue_category: 'accessory',
        primary_muscles: [],
        secondary_muscles: [],
        equipment: 'barbell',
        cues: [],
        notes: '',
      })
      setFatigueProfile(null)
      setFatigueSource(null)
      setFatigueReasoning(null)
      loadExercises()
    } catch (err) {
      pushToast({ message: 'Failed to save exercise', type: 'error' })
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this exercise?')) return

    try {
      await api.deleteExercise(id)
      pushToast({ message: 'Exercise deleted', type: 'success' })
      setExercises((prev) => prev.filter((e) => e.id !== id))
    } catch (err) {
      pushToast({ message: 'Failed to delete exercise', type: 'error' })
    }
  }

  function startEdit(exercise: GlossaryExercise) {
    setIsEditing(exercise)
    setFormData({
      name: exercise.name,
      category: exercise.category,
      fatigue_category: exercise.fatigue_category || 'accessory',
      primary_muscles: exercise.primary_muscles,
      secondary_muscles: exercise.secondary_muscles,
      equipment: exercise.equipment,
      cues: exercise.cues,
      notes: exercise.notes,
    })
    setFatigueProfile(exercise.fatigue_profile || null)
    setFatigueSource(exercise.fatigue_profile_source || null)
    setFatigueReasoning(exercise.fatigue_profile_reasoning || null)
    setShowAddForm(true)
  }

  function addCue() {
    if (!cueInput.trim()) return
    setFormData((prev) => ({
      ...prev,
      cues: [...(prev.cues || []), cueInput.trim()],
    }))
    setCueInput('')
  }

  function removeCue(index: number) {
    setFormData((prev) => ({
      ...prev,
      cues: (prev.cues || []).filter((_, i) => i !== index),
    }))
  }

  function toggleMuscle(muscle: MuscleGroup, field: 'primary_muscles' | 'secondary_muscles') {
    setFormData((prev) => {
      const current = prev[field] || []
      const exists = current.includes(muscle)
      return {
        ...prev,
        [field]: exists
          ? current.filter((m) => m !== muscle)
          : [...current, muscle],
      }
    })
  }

  function handleFatigueSliderChange(dimension: keyof FatigueProfile, value: number) {
    setFatigueProfile((prev) => {
      const next = prev
        ? { ...prev, [dimension]: value / 100 }
        : { axial: 0, neural: 0, peripheral: 0, systemic: 0, [dimension]: value / 100 }
      return next as FatigueProfile
    })
    setFatigueSource('manual')
    setFatigueReasoning(null)
  }

  async function handleReEstimate() {
    setIsEstimating(true)
    try {
      const result = await api.estimateFatigueProfile({
        name: formData.name || '',
        category: formData.category,
        equipment: formData.equipment,
        primary_muscles: formData.primary_muscles,
        secondary_muscles: formData.secondary_muscles,
        cues: formData.cues,
        notes: formData.notes,
      })
      setFatigueProfile({
        axial: result.axial,
        neural: result.neural,
        peripheral: result.peripheral,
        systemic: result.systemic,
      })
      setFatigueSource('ai_estimated')
      setFatigueReasoning(result.reasoning)
    } catch {
      pushToast({ message: 'Fatigue estimation failed', type: 'error' })
    } finally {
      setIsEstimating(false)
    }
  }

  const filteredExercises = useMemo(() => {
    if (!searchQuery.trim()) return exercises
    const query = searchQuery.toLowerCase()
    return exercises.filter(
      (e) =>
        e.name.toLowerCase().includes(query) ||
        e.category.toLowerCase().includes(query) ||
        e.primary_muscles.some((m) => m.toLowerCase().includes(query))
    )
  }, [exercises, searchQuery])

  const groupedExercises = useMemo(() => {
    const groups: Record<ExerciseCategory, GlossaryExercise[]> = {
      squat: [],
      bench: [],
      deadlift: [],
      back: [],
      chest: [],
      arm: [],
      legs: [],
      core: [],
      lower_back: [],
    }
    for (const exercise of filteredExercises) {
      groups[exercise.category].push(exercise)
    }
    return groups
  }, [filteredExercises])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-pulse text-muted-foreground">Loading exercises...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Exercise Glossary</h1>
          <p className="text-muted-foreground">
            Browse and manage exercise definitions
          </p>
        </div>
        <button
          onClick={() => {
            setShowAddForm(true)
            setIsEditing(null)
            setFormData({
              name: '',
              category: 'squat',
              primary_muscles: [],
              secondary_muscles: [],
              equipment: 'barbell',
              cues: [],
              notes: '',
            })
          }}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium"
        >
          <Plus className="w-4 h-4" />
          Add Exercise
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search exercises..."
          className="w-full pl-10 pr-4 py-2 border border-border rounded-lg bg-background"
        />
      </div>

      {/* Add/Edit Form */}
      {showAddForm && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">{isEditing ? 'Edit Exercise' : 'Add New Exercise'}</h3>
            <button
              onClick={() => {
                setShowAddForm(false)
                setIsEditing(null)
              }}
              className="p-1 hover:bg-accent rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">Name</label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-border rounded-md bg-background"
              />
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Category</label>
              <select
                value={formData.category || 'squat'}
                onChange={(e) => setFormData((p) => ({ ...p, category: e.target.value as ExerciseCategory }))}
                className="w-full px-3 py-2 border border-border rounded-md bg-background"
              >
                {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-sm text-muted-foreground">Equipment</label>
            <select
              value={formData.equipment || 'barbell'}
              onChange={(e) => setFormData((p) => ({ ...p, equipment: e.target.value as Equipment }))}
              className="w-full px-3 py-2 border border-border rounded-md bg-background"
            >
              {Object.entries(EQUIPMENT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm text-muted-foreground">Fatigue Category</label>
            <select
              value={formData.fatigue_category || 'accessory'}
              onChange={(e) => setFormData((p) => ({ ...p, fatigue_category: e.target.value as FatigueCategory }))}
              className="w-full px-3 py-2 border border-border rounded-md bg-background"
            >
              {FATIGUE_CATEGORY_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Fatigue Profile Sliders */}
          <div className="space-y-3 border border-border rounded-md p-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Fatigue Profile</label>
              <div className="flex items-center gap-2">
                {fatigueSource && (
                  <span className={clsx(
                    'text-xs px-2 py-0.5 rounded-full',
                    fatigueSource === 'ai_estimated'
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                      : 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                  )}>
                    {fatigueSource === 'ai_estimated' ? 'AI estimated' : 'Manual override'}
                  </span>
                )}
                <button
                  type="button"
                  onClick={handleReEstimate}
                  disabled={isEstimating || !formData.name}
                  className="flex items-center gap-1 px-2 py-1 text-xs bg-secondary rounded-md hover:bg-secondary/80 disabled:opacity-50"
                >
                  <RefreshCw className={clsx('w-3 h-3', isEstimating && 'animate-spin')} />
                  {isEstimating ? 'Estimating...' : 'Re-estimate'}
                </button>
              </div>
            </div>
            <FatigueSlider
              label="Axial (spinal loading)"
              value={Math.round((fatigueProfile?.axial ?? 0) * 100)}
              onChange={(v) => handleFatigueSliderChange('axial', v)}
            />
            <FatigueSlider
              label="Neural (CNS demand)"
              value={Math.round((fatigueProfile?.neural ?? 0) * 100)}
              onChange={(v) => handleFatigueSliderChange('neural', v)}
            />
            <FatigueSlider
              label="Peripheral (muscle damage)"
              value={Math.round((fatigueProfile?.peripheral ?? 0) * 100)}
              onChange={(v) => handleFatigueSliderChange('peripheral', v)}
            />
            <FatigueSlider
              label="Systemic (metabolic load)"
              value={Math.round((fatigueProfile?.systemic ?? 0) * 100)}
              onChange={(v) => handleFatigueSliderChange('systemic', v)}
            />
            {fatigueSource === 'ai_estimated' && fatigueReasoning && (
              <p className="text-xs text-muted-foreground italic">{fatigueReasoning}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">Primary Muscles</label>
              <div className="flex flex-wrap gap-1 mt-1">
                {Object.entries(MUSCLE_LABELS).map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => toggleMuscle(value as MuscleGroup, 'primary_muscles')}
                    className={clsx(
                      'px-2 py-1 text-xs rounded-md',
                      formData.primary_muscles?.includes(value as MuscleGroup)
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-secondary text-secondary-foreground'
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Secondary Muscles</label>
              <div className="flex flex-wrap gap-1 mt-1">
                {Object.entries(MUSCLE_LABELS).map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => toggleMuscle(value as MuscleGroup, 'secondary_muscles')}
                    className={clsx(
                      'px-2 py-1 text-xs rounded-md',
                      formData.secondary_muscles?.includes(value as MuscleGroup)
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-secondary text-secondary-foreground'
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="text-sm text-muted-foreground">Cues</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={cueInput}
                onChange={(e) => setCueInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addCue()}
                placeholder="Add a cue..."
                className="flex-1 px-3 py-2 border border-border rounded-md bg-background"
              />
              <button
                onClick={addCue}
                className="px-3 py-2 bg-secondary rounded-md"
              >
                Add
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {formData.cues?.map((cue, i) => (
                <span
                  key={i}
                  className="flex items-center gap-1 px-2 py-1 bg-secondary rounded-md text-sm"
                >
                  {cue}
                  <button onClick={() => removeCue(i)} className="hover:text-destructive">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm text-muted-foreground">Notes</label>
            <textarea
              value={formData.notes || ''}
              onChange={(e) => setFormData((p) => ({ ...p, notes: e.target.value }))}
              rows={3}
              className="w-full px-3 py-2 border border-border rounded-md bg-background resize-none"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={() => {
                setShowAddForm(false)
                setIsEditing(null)
              }}
              className="px-4 py-2 bg-secondary rounded-md"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium"
            >
              {isEditing ? 'Update' : 'Add'} Exercise
            </button>
          </div>
        </div>
      )}

      {/* Exercise List by Category */}
      {Object.entries(groupedExercises).map(([category, categoryExercises]) => {
        if (categoryExercises.length === 0) return null

        return (
          <div key={category} className="space-y-2">
            <h2 className="text-lg font-semibold">
              {CATEGORY_LABELS[category as ExerciseCategory]}
              <span className="text-sm font-normal text-muted-foreground ml-2">
                ({categoryExercises.length})
              </span>
            </h2>

            <div className="space-y-2">
              {categoryExercises.map((exercise) => (
                <div
                  key={exercise.id}
                  className="bg-card border border-border rounded-lg overflow-hidden"
                >
                  <button
                    onClick={() => setExpandedId(expandedId === exercise.id ? null : exercise.id)}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-accent/50"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-medium">{exercise.name}</span>
                      <span className="text-xs px-2 py-0.5 bg-secondary rounded">
                        {EQUIPMENT_LABELS[exercise.equipment]}
                      </span>
                      <span className="text-xs px-2 py-0.5 bg-muted text-muted-foreground rounded">
                        {FATIGUE_LABELS[exercise.fatigue_category || 'accessory']}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1">
                        {exercise.primary_muscles.slice(0, 3).map((m) => (
                          <span
                            key={m}
                            className="text-xs px-2 py-0.5 bg-primary/20 text-primary rounded"
                          >
                            {MUSCLE_LABELS[m]}
                          </span>
                        ))}
                        {exercise.primary_muscles.length > 3 && (
                          <span className="text-xs text-muted-foreground">
                            +{exercise.primary_muscles.length - 3}
                          </span>
                        )}
                      </div>
                      {expandedId === exercise.id ? (
                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      )}
                    </div>
                  </button>

                  {expandedId === exercise.id && (
                    <div className="px-4 pb-4 pt-2 border-t border-border space-y-4">
                      {/* Muscles */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Primary Muscles</p>
                          <div className="flex flex-wrap gap-1">
                            {exercise.primary_muscles.map((m) => (
                              <span
                                key={m}
                                className="text-xs px-2 py-0.5 bg-primary/20 text-primary rounded"
                              >
                                {MUSCLE_LABELS[m]}
                              </span>
                            ))}
                          </div>
                        </div>
                        {exercise.secondary_muscles.length > 0 && (
                          <div>
                            <p className="text-xs text-muted-foreground mb-1">Secondary Muscles</p>
                            <div className="flex flex-wrap gap-1">
                              {exercise.secondary_muscles.map((m) => (
                                <span
                                  key={m}
                                  className="text-xs px-2 py-0.5 bg-secondary rounded"
                                >
                                  {MUSCLE_LABELS[m]}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Cues */}
                      {exercise.cues.length > 0 && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Cues</p>
                          <ul className="list-disc list-inside text-sm space-y-1">
                            {exercise.cues.map((cue, i) => (
                              <li key={i}>{cue}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Notes */}
                      {exercise.notes && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Notes</p>
                          <p className="text-sm">{exercise.notes}</p>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex gap-2 pt-2">
                        <button
                          onClick={() => startEdit(exercise)}
                          className="flex items-center gap-1 px-3 py-1 text-sm bg-secondary rounded-md hover:bg-secondary/80"
                        >
                          <Edit2 className="w-3 h-3" />
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(exercise.id)}
                          className="flex items-center gap-1 px-3 py-1 text-sm bg-destructive/10 text-destructive rounded-md hover:bg-destructive/20"
                        >
                          <Trash2 className="w-3 h-3" />
                          Delete
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}

      {filteredExercises.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          {searchQuery ? 'No exercises found matching your search.' : 'No exercises in the glossary yet.'}
        </div>
      )}
    </div>
  )
}
