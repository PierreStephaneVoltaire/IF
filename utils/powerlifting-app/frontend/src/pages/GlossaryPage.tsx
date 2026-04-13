import { useState, useEffect, useMemo } from 'react'
import { Search, Plus, X, Trash2, Edit2, RefreshCw } from 'lucide-react'
import {
  Stack,
  Group,
  Text,
  TextInput,
  Textarea,
  Select,
  Button,
  Badge,
  Modal,
  Paper,
  Accordion,
  Slider,
  ActionIcon,
  Loader,
  CloseButton,
  SimpleGrid,
} from '@mantine/core'
import * as api from '@/api/client'
import { useUiStore } from '@/store/uiStore'
import type { GlossaryExercise, MuscleGroup, ExerciseCategory, Equipment, FatigueProfile, FatigueProfileSource } from '@powerlifting/types'

interface FatigueSliderProps {
  label: string
  value: number
  onChange: (v: number) => void
}

function FatigueSlider({ label, value, onChange }: FatigueSliderProps) {
  return (
    <Stack gap={4}>
      <Group justify="space-between">
        <Text size="sm" c="dimmed">{label}</Text>
        <Text size="xs" ff="monospace">{(value / 100).toFixed(2)}</Text>
      </Group>
      <Slider
        min={0}
        max={100}
        step={5}
        value={value}
        onChange={onChange}
      />
    </Stack>
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
        fatigue_category: (isEditing as GlossaryExercise | null)?.fatigue_category || 'accessory',
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
      <Group justify="center" py={48}>
        <Loader />
      </Group>
    )
  }

  return (
    <Stack gap={24}>
      <Group justify="space-between">
        <div>
          <Text fz="h1" fw={700}>Exercise Glossary</Text>
          <Text c="dimmed">Browse and manage exercise definitions</Text>
        </div>
        <Button
          leftSection={<Plus size={16} />}
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
        >
          Add Exercise
        </Button>
      </Group>

      {/* Search */}
      <TextInput
        leftSection={<Search size={16} />}
        placeholder="Search exercises..."
        value={searchQuery}
        onChange={(e) => handleSearch(e.currentTarget.value)}
      />

      {/* Add/Edit Form Modal */}
      <Modal
        opened={showAddForm}
        onClose={() => { setShowAddForm(false); setIsEditing(null) }}
        title={isEditing ? 'Edit Exercise' : 'Add New Exercise'}
        size="xl"
      >
        <Stack gap="md">
          <SimpleGrid cols={2} spacing="md" breakpoints={[{ maxWidth: 'sm', cols: 1 }]}>
            <div>
              <Text size="sm" c="dimmed" mb={4}>Name</Text>
              <TextInput
                value={formData.name || ''}
                onChange={(e) => setFormData((p) => ({ ...p, name: e.currentTarget.value }))}
              />
            </div>
            <div>
              <Text size="sm" c="dimmed" mb={4}>Category</Text>
              <Select
                value={formData.category || 'squat'}
                onChange={(v) => setFormData((p) => ({ ...p, category: (v || 'squat') as ExerciseCategory }))}
                data={Object.entries(CATEGORY_LABELS).map(([value, label]) => ({ value, label }))}
              />
            </div>
          </SimpleGrid>

          <div>
            <Text size="sm" c="dimmed" mb={4}>Equipment</Text>
            <Select
              value={formData.equipment || 'barbell'}
              onChange={(v) => setFormData((p) => ({ ...p, equipment: (v || 'barbell') as Equipment }))}
              data={Object.entries(EQUIPMENT_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </div>

          {/* Fatigue Profile Sliders */}
          <Paper withBorder p="md">
            <Group justify="space-between" mb="sm">
              <Text size="sm" fw={500}>Fatigue Profile</Text>
              <Group gap="xs">
                {fatigueSource && (
                  <Badge
                    variant="light"
                    color={fatigueSource === 'ai_estimated' ? 'blue' : 'green'}
                  >
                    {fatigueSource === 'ai_estimated' ? 'AI estimated' : 'Manual override'}
                  </Badge>
                )}
                <Button
                  size="compact-xs"
                  variant="default"
                  onClick={handleReEstimate}
                  disabled={isEstimating || !formData.name}
                  leftSection={isEstimating ? <Loader size={12} /> : <RefreshCw size={12} />}
                >
                  {isEstimating ? 'Estimating...' : 'Re-estimate'}
                </Button>
              </Group>
            </Group>
            <Stack gap="sm">
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
            </Stack>
            {fatigueSource === 'ai_estimated' && fatigueReasoning && (
              <Text size="xs" c="dimmed" fs="italic" mt="xs">{fatigueReasoning}</Text>
            )}
          </Paper>

          <SimpleGrid cols={2} spacing="md" breakpoints={[{ maxWidth: 'lg', cols: 1 }]}>
            <div>
              <Text size="sm" c="dimmed" mb={4}>Primary Muscles</Text>
              <Group gap={4} style={{ maxHeight: 224, overflowY: 'auto', flexWrap: 'wrap' }}>
                {Object.entries(MUSCLE_LABELS).map(([value, label]) => (
                  <Button
                    key={value}
                    size="compact-xs"
                    variant={formData.primary_muscles?.includes(value as MuscleGroup) ? 'filled' : 'default'}
                    onClick={() => toggleMuscle(value as MuscleGroup, 'primary_muscles')}
                  >
                    {label}
                  </Button>
                ))}
              </Group>
            </div>
            <div>
              <Text size="sm" c="dimmed" mb={4}>Secondary Muscles</Text>
              <Group gap={4} style={{ maxHeight: 224, overflowY: 'auto', flexWrap: 'wrap' }}>
                {Object.entries(MUSCLE_LABELS).map(([value, label]) => (
                  <Button
                    key={value}
                    size="compact-xs"
                    variant={formData.secondary_muscles?.includes(value as MuscleGroup) ? 'filled' : 'default'}
                    onClick={() => toggleMuscle(value as MuscleGroup, 'secondary_muscles')}
                  >
                    {label}
                  </Button>
                ))}
              </Group>
            </div>
          </SimpleGrid>

          <div>
            <Text size="sm" c="dimmed" mb={4}>Cues</Text>
            <Group gap="xs" mb="xs">
              <TextInput
                placeholder="Add a cue..."
                value={cueInput}
                onChange={(e) => setCueInput(e.currentTarget.value)}
                onKeyDown={(e) => e.key === 'Enter' && addCue()}
                style={{ flex: 1 }}
              />
              <Button variant="default" onClick={addCue}>Add</Button>
            </Group>
            <Group gap="xs">
              {formData.cues?.map((cue, i) => (
                <Badge
                  key={i}
                  variant="light"
                  rightSection={
                    <CloseButton
                      size="xs"
                      variant="transparent"
                      onClick={() => removeCue(i)}
                    />
                  }
                >
                  {cue}
                </Badge>
              ))}
            </Group>
          </div>

          <div>
            <Text size="sm" c="dimmed" mb={4}>Notes</Text>
            <Textarea
              autosize
              minRows={3}
              value={formData.notes || ''}
              onChange={(e) => setFormData((p) => ({ ...p, notes: e.currentTarget.value }))}
            />
          </div>

          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => {
                setShowAddForm(false)
                setIsEditing(null)
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleSave}>
              {isEditing ? 'Update' : 'Add'} Exercise
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Exercise List by Category */}
      {Object.entries(groupedExercises).map(([category, categoryExercises]) => {
        if (categoryExercises.length === 0) return null

        return (
          <Stack key={category} gap="xs">
            <Group gap="xs">
              <Text fz="h2" fw={600}>{CATEGORY_LABELS[category as ExerciseCategory]}</Text>
              <Text size="sm" c="dimmed">({categoryExercises.length})</Text>
            </Group>

            <Accordion
              variant="contained"
              chevronPosition="right"
            >
              {categoryExercises.map((exercise) => (
                <Accordion.Item key={exercise.id} value={exercise.id}>
                  <Accordion.Control>
                    <Group gap="sm" wrap="nowrap">
                      <Text fw={500}>{exercise.name}</Text>
                      <Badge variant="light" color="gray" size="sm">
                        {EQUIPMENT_LABELS[exercise.equipment]}
                      </Badge>
                      {exercise.fatigue_profile && (
                        <Badge variant="light" color="blue" size="sm">
                          {exercise.fatigue_profile_source === 'ai_estimated' ? 'AI' : 'Manual'}
                        </Badge>
                      )}
                    </Group>
                  </Accordion.Control>
                  <Accordion.Content>
                    <Stack gap="md">
                      {/* Muscles */}
                      <SimpleGrid cols={2} spacing="md">
                        <div>
                          <Text size="xs" c="dimmed" mb={4}>Primary Muscles</Text>
                          <Group gap={4}>
                            {exercise.primary_muscles.map((m) => (
                              <Badge key={m} variant="light" size="sm">
                                {MUSCLE_LABELS[m]}
                              </Badge>
                            ))}
                          </Group>
                        </div>
                        {exercise.secondary_muscles.length > 0 && (
                          <div>
                            <Text size="xs" c="dimmed" mb={4}>Secondary Muscles</Text>
                            <Group gap={4}>
                              {exercise.secondary_muscles.map((m) => (
                                <Badge key={m} variant="outline" size="sm">
                                  {MUSCLE_LABELS[m]}
                                </Badge>
                              ))}
                            </Group>
                          </div>
                        )}
                      </SimpleGrid>

                      {/* Cues */}
                      {exercise.cues.length > 0 && (
                        <div>
                          <Text size="xs" c="dimmed" mb={4}>Cues</Text>
                          <Stack gap={4}>
                            {exercise.cues.map((cue, i) => (
                              <Text key={i} size="sm">- {cue}</Text>
                            ))}
                          </Stack>
                        </div>
                      )}

                      {/* Notes */}
                      {exercise.notes && (
                        <div>
                          <Text size="xs" c="dimmed" mb={4}>Notes</Text>
                          <Text size="sm">{exercise.notes}</Text>
                        </div>
                      )}

                      {/* Actions */}
                      <Group gap="xs">
                        <Button
                          size="compact-sm"
                          variant="default"
                          leftSection={<Edit2 size={12} />}
                          onClick={() => startEdit(exercise)}
                        >
                          Edit
                        </Button>
                        <Button
                          size="compact-sm"
                          variant="light"
                          color="red"
                          leftSection={<Trash2 size={12} />}
                          onClick={() => handleDelete(exercise.id)}
                        >
                          Delete
                        </Button>
                      </Group>
                    </Stack>
                  </Accordion.Content>
                </Accordion.Item>
              ))}
            </Accordion>
          </Stack>
        )
      })}

      {filteredExercises.length === 0 && (
        <Text ta="center" py={48} c="dimmed">
          {searchQuery ? 'No exercises found matching your search.' : 'No exercises in the glossary yet.'}
        </Text>
      )}
    </Stack>
  )
}
