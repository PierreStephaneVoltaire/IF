import { useState, useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Trash2, X, Save, BarChart3, Copy, ArrowLeft, ArrowRight } from 'lucide-react'
import {
  Stack, Group, Text, Button, Paper, Badge, Modal, SimpleGrid,
  TextInput, NumberInput, Select, ActionIcon, Autocomplete, Progress, Box, Divider
} from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import { useSettingsStore } from '@/store/settingsStore'
import { normalizeExerciseName } from '@/utils/volume'
import { toDisplayUnit, fromDisplayUnit, displayWeight } from '@/utils/units'
import * as api from '@/api/client'
import type { Session, PlannedExercise, GlossaryExercise } from '@powerlifting/types'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const MUSCLE_LABELS: Record<string, string> = {
  quads: 'Quads',
  hamstrings: 'Hamstrings',
  glutes: 'Glutes',
  calves: 'Calves',
  tibialis_anterior: 'Tibialis Anterior',
  hip_flexors: 'Hip Flexors',
  adductors: 'Adductors',
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
  serratus: 'Serratus',
}

const STATUS_COLORS: Record<string, string> = {
  planned: 'blue',
  completed: 'green',
  logged: 'yellow',
  skipped: 'gray',
}

// Helper to add IDs to planned exercises for stable DND
interface PlannedExerciseWithId extends PlannedExercise {
  id: string
}

import { LoadTypeBadge } from '@/components/shared/LoadTypeBadge'

function SortableExercise({ ex, onRemove, onUpdate }: { 
  ex: PlannedExerciseWithId; 
  onRemove: (id: string) => void;
  onUpdate: (id: string, f: keyof PlannedExercise, v: any) => void;
}) {
  const { unit } = useSettingsStore()
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: ex.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 1000 : undefined,
    opacity: isDragging ? 0.5 : 1,
  }

  const renderLoadInput = () => {
    switch (ex.load_source) {
      case 'rpe':
        return (
          <NumberInput
            value={ex.rpe_target || ''}
            onChange={(v) => onUpdate(ex.id, 'rpe_target', Number(v) || null)}
            min={0}
            max={10}
            step={0.5}
            w={70}
            placeholder="RPE"
          />
        )
      case 'percentage':
        return (
          <Group gap={4} wrap="nowrap">
            <Text size="xs" c="dimmed">~</Text>
            <NumberInput
              value={ex.kg !== null ? toDisplayUnit(ex.kg, unit) : ''}
              onChange={(v) => onUpdate(ex.id, 'kg', v !== '' ? fromDisplayUnit(Number(v), unit) : null)}
              min={0}
              w={70}
              placeholder={unit}
              decimalScale={unit === 'lb' ? 1 : 2}
            />
          </Group>
        )
      case 'unresolvable':
        return <Text size="sm" c="dimmed">—</Text>
      case 'absolute':
      default:
        return (
          <NumberInput
            value={ex.kg !== null ? toDisplayUnit(ex.kg, unit) : ''}
            onChange={(v) => onUpdate(ex.id, 'kg', v !== '' ? fromDisplayUnit(Number(v), unit) : null)}
            min={0}
            w={70}
            placeholder={unit}
            decimalScale={unit === 'lb' ? 1 : 2}
          />
        )
    }
  }

  return (
    <Paper ref={setNodeRef} style={style} withBorder p="xs" radius="sm">
      <Group justify="space-between" gap="xs" mb={4}>
        <Group gap="xs" style={{ flex: 1 }}>
          <Box {...attributes} {...listeners} style={{ cursor: 'grab', padding: '4px 0' }}>
            <Group gap={2}>
              <Box style={{ width: 2, height: 12, background: 'var(--mantine-color-gray-4)' }} />
              <Box style={{ width: 2, height: 12, background: 'var(--mantine-color-gray-4)' }} />
            </Group>
          </Box>
          <Text size="sm" fw={500} truncate>{ex.name}</Text>
          {ex.load_source && <LoadTypeBadge source={ex.load_source} />}
        </Group>
        <ActionIcon
          variant="subtle"
          color="red"
          size="sm"
          onClick={() => onRemove(ex.id)}
        >
          <Trash2 size={12} />
        </ActionIcon>
      </Group>
      <Group gap={6}>
        <NumberInput
          value={ex.sets}
          onChange={(v) => onUpdate(ex.id, 'sets', Number(v) || 0)}
          min={0}
          w={60}
          placeholder="Sets"
        />
        <Text size="xs" c="dimmed">x</Text>
        <NumberInput
          value={ex.reps}
          onChange={(v) => onUpdate(ex.id, 'reps', Number(v) || 0)}
          min={0}
          w={60}
          placeholder="Reps"
        />
        <Text size="xs" c="dimmed">@</Text>
        {renderLoadInput()}
      </Group>
    </Paper>
  )
}

export default function DesignerPage() {
  const { program, version, createSession } = useProgramStore()
  const { pushToast } = useUiStore()
  const { unit } = useSettingsStore()
  const [searchParams] = useSearchParams()

  const [block, setBlock] = useState('current')
  const [selectedWeek, setSelectedWeek] = useState(1)
  const [editingSession, setEditingSession] = useState<Session | null>(null)
  const [editingSessionGlobalIndex, setEditingSessionGlobalIndex] = useState<number>(-1)
  const [editingSessionDate, setEditingSessionDate] = useState<string>('')
  const [isSessionEditorOpen, setIsSessionEditorOpen] = useState(false)
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [exerciseSearch, setExerciseSearch] = useState('')

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (over && active.id !== over.id) {
      setPlannedExercises((items) => {
        const oldIndex = items.findIndex(i => i.id === active.id)
        const newIndex = items.findIndex(i => i.id === over.id)
        return arrayMove(items, oldIndex, newIndex)
      })
    }
  }

  // Session form state
  const [sessionDate, setSessionDate] = useState<string | null>(null)
  const [sessionDay, setSessionDay] = useState('Monday')
  const [sessionWeek, setSessionWeek] = useState('W1')
  const [sessionPhase, setSessionPhase] = useState('')
  const [plannedExercises, setPlannedExercises] = useState<PlannedExerciseWithId[]>([])

  const phases = program?.phases || []

  useEffect(() => {
    api.fetchGlossary().then(setGlossary).catch(console.error)
  }, [])

  // Read week from URL query params
  useEffect(() => {
    const weekParam = searchParams.get('week')
    if (weekParam) {
      const week = parseInt(weekParam, 10)
      if (!isNaN(week) && week > 0) {
        setSelectedWeek(week)
      }
    }
  }, [searchParams])

  const totalWeeks = useMemo(() => {
    if (!phases.length) return 12
    return Math.max(...phases.map(p => p.end_week))
  }, [phases])

  const weekOptions = useMemo(() => {
    return Array.from({ length: totalWeeks }, (_, i) => i + 1)
  }, [totalWeeks])

  const blocks = useMemo(() => {
    const s = new Set<string>()
    for (const session of (program?.sessions || [])) s.add(session.block ?? 'current')
    return Array.from(s)
  }, [program?.sessions])

  const weekSessions = useMemo(() => {
    return (program?.sessions || [])
      .filter(s => s.week_number === selectedWeek)
      .filter(s => (s.block ?? 'current') === block)
  }, [program?.sessions, selectedWeek, block])

  const plannedMuscleVolume = useMemo(() => {
    const mgSets: Record<string, number> = {}
    const lookup = new Map<string, { primary: string[]; secondary: string[]; tertiary: string[] }>()
    for (const ex of glossary) {
      lookup.set(normalizeExerciseName(ex.name), {
        primary: ex.primary_muscles,
        secondary: ex.secondary_muscles,
        tertiary: ex.tertiary_muscles ?? [],
      })
    }

    for (const s of weekSessions) {
      for (const ex of s.planned_exercises || []) {
        const muscles = lookup.get(normalizeExerciseName(ex.name))
        if (!muscles) continue
        const sets = ex.sets || 0
        for (const m of muscles.primary) mgSets[m] = (mgSets[m] || 0) + sets
        for (const m of muscles.secondary) mgSets[m] = (mgSets[m] || 0) + sets * 0.5
        for (const m of muscles.tertiary) mgSets[m] = (mgSets[m] || 0) + sets * 0.25
      }
    }

    const sorted = Object.entries(mgSets)
      .sort(([, a], [, b]) => b - a)
      .map(([muscle, sets]) => ({ label: MUSCLE_LABELS[muscle] || muscle, sets }))

    if (sorted.length <= 5) return sorted
    const top5 = sorted.slice(0, 5)
    const others = sorted.slice(5).reduce((sum, item) => sum + item.sets, 0)
    return [...top5, { label: 'Others', sets: others }]
  }, [weekSessions, glossary])

  // Copy session state
  const [copySourceWeek, setCopySourceWeek] = useState<number | null>(null)
  const [isCopyModalOpen, setIsCopyModalOpen] = useState(false)
  const [copyCollisionMode, setCopyCollisionMode] = useState<'overwrite' | 'add'>('add')

  async function handleCopySessions(sourceWeek: number) {
    if (sourceWeek === selectedWeek) return
    const sourceSessions = (program?.sessions || [])
      .filter(s => s.week_number === sourceWeek)
      .filter(s => (s.block ?? 'current') === block)
    
    if (sourceSessions.length === 0) {
      pushToast({ message: `No sessions found in Week ${sourceWeek}`, type: 'error' })
      return
    }

    setCopySourceWeek(sourceWeek)
    setIsCopyModalOpen(true)
  }

  async function executeCopy() {
    if (!copySourceWeek) return
    try {
      const sourceSessions = (program?.sessions || [])
        .filter(s => s.week_number === copySourceWeek)
        .filter(s => (s.block ?? 'current') === block)
      
      const targetSessions = weekSessions
      
      for (const src of sourceSessions) {
        // Find if target session exists on same day
        const existing = targetSessions.find(t => t.day === src.day)
        
        if (existing) {
          if (existing.completed) {
            console.log(`Skipping completed session on ${existing.day}`)
            continue
          }

          if (copyCollisionMode === 'overwrite') {
            await api.updatePlannedExercises(version, existing.date, program?.sessions.indexOf(existing) ?? -1, src.planned_exercises || [])
          } else {
            const combined = [...(existing.planned_exercises || []), ...(src.planned_exercises || [])]
            await api.updatePlannedExercises(version, existing.date, program?.sessions.indexOf(existing) ?? -1, combined)
          }
        } else {
          // Create new session for that day in the target week
          const dayIndex = DAYS.indexOf(src.day)
          const programStart = new Date(program?.meta?.program_start || new Date().toISOString())
          const targetDate = new Date(programStart)
          targetDate.setDate(targetDate.getDate() + (selectedWeek - 1) * 7 + dayIndex)
          const dateStr = targetDate.toISOString().slice(0, 10)

          await api.createSession(version, {
            date: dateStr,
            day: src.day,
            week: `W${selectedWeek}`,
            block: block,
            status: 'planned',
            completed: false,
            planned_exercises: src.planned_exercises || [],
            exercises: [],
          })
        }
      }

      setIsCopyModalOpen(false)
      pushToast({ message: `Sessions copied from Week ${copySourceWeek}`, type: 'success' })
      useProgramStore.getState().loadProgram(version)
    } catch (err) {
      console.error('Copy failed:', err)
      pushToast({ message: 'Failed to copy sessions', type: 'error' })
    }
  }

  function openSessionEditor(session?: Session, date?: string, index?: number) {
    if (session) {
      setEditingSession(session)
      setEditingSessionDate(session.date)
      setEditingSessionGlobalIndex(
        index !== undefined && index >= 0
          ? program?.sessions.indexOf(session) ?? -1
          : program?.sessions.findIndex(s => s.date === session.date && s.week_number === session.week_number && s.day === session.day) ?? -1
      )
      setSessionDate(session.date)
      setSessionDay(session.day)
      setSessionWeek(session.week)
      setSessionPhase(typeof session.phase === 'string' ? session.phase : session.phase?.name || '')
      setPlannedExercises((session.planned_exercises || []).map((ex, i) => ({ ...ex, id: `ex-${Date.now()}-${i}` })))
    } else {
      setEditingSession(null)
      setEditingSessionDate('')
      setEditingSessionGlobalIndex(-1)
      const dayName = DAYS[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]
      setSessionDate(new Date().toISOString().slice(0, 10))
      setSessionDay(dayName)
      setSessionWeek(`W${selectedWeek}`)
      const phaseParam = searchParams.get('phase')
      setSessionPhase(phaseParam || phases[0]?.name || '')
      setPlannedExercises([])
    }
    setIsSessionEditorOpen(true)
  }

  function closeSessionEditor() {
    setEditingSession(null)
    setEditingSessionDate('')
    setEditingSessionGlobalIndex(-1)
    setIsSessionEditorOpen(false)
    setPlannedExercises([])
    setExerciseSearch('')
  }

  async function saveSession() {
    try {
      const dateStr = sessionDate ?? new Date().toISOString().slice(0, 10)
      
      // Strip IDs before saving
      const exercisesToSave = plannedExercises.map(({ id, ...rest }) => rest)

      const sessionData: Partial<Session> & { date: string } = {
        date: dateStr,
        day: sessionDay,
        week: sessionWeek,
        status: 'planned',
        completed: false,
        planned_exercises: exercisesToSave,
        exercises: [],
        session_notes: '',
      }

      if (editingSession) {
        if (editingSessionGlobalIndex < 0) {
          throw new Error('Could not resolve the session index for update')
        }
        await api.updatePlannedExercises(version, editingSessionDate, editingSessionGlobalIndex, exercisesToSave)
      } else {
        await createSession(sessionData)
      }

      closeSessionEditor()
      useProgramStore.getState().loadProgram(version)
    } catch (err) {
      console.error('Failed to save session:', err)
      pushToast({ message: 'Failed to save session', type: 'error' })
    }
  }

  function addPlannedExercise(exercise: GlossaryExercise) {
    setPlannedExercises(prev => [...prev, {
      id: `ex-${Date.now()}-${prev.length}`,
      name: exercise.name,
      sets: 3,
      reps: 5,
      kg: null,
    }])
    setExerciseSearch('')
  }

  function updatePlannedExercise(id: string, field: keyof PlannedExercise, value: unknown) {
    setPlannedExercises(prev => prev.map((pe) => pe.id === id ? { ...pe, [field]: value } : pe))
  }

  function removePlannedExercise(id: string) {
    setPlannedExercises(prev => prev.filter((ex) => ex.id !== id))
  }

  const filteredGlossary = useMemo(() => {
    if (!exerciseSearch.trim()) return glossary.slice(0, 10)
    const q = exerciseSearch.toLowerCase()
    return glossary.filter(e => e.name.toLowerCase().includes(q)).slice(0, 10)
  }, [glossary, exerciseSearch])

  const autocompleteData = useMemo(() => filteredGlossary.map(e => e.name), [filteredGlossary])

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          <Text component={Link} to="/designer" size="sm" c="dimmed">Designer</Text>
          <Text c="dimmed">/</Text>
          <Text fw={700} size="xl">Session Design</Text>
        </Group>
        <Group gap="sm" wrap="wrap">
          {blocks.length > 1 && (
            <Select
              value={block}
              onChange={(v) => setBlock(v ?? 'current')}
              data={blocks.map(b => ({ value: b, label: b === 'current' ? 'Current Block' : b }))}
              size="sm"
              w={160}
            />
          )}
          <Select
            value={String(selectedWeek)}
            onChange={(v) => setSelectedWeek(Number(v ?? 1))}
            data={weekOptions.map(w => ({ value: String(w), label: `Week ${w}` }))}
            size="sm"
            w={120}
          />
          <Button
            leftSection={<Plus size={16} />}
            size="sm"
            onClick={() => openSessionEditor()}
          >
            Add Session
          </Button>
        </Group>
      </Group>

      {/* Week Navigation & Copy Buttons */}
      <Group justify="space-between" wrap="nowrap">
        <Group gap="xs">
          <Button 
            variant="default" 
            size="compact-sm" 
            leftSection={<ArrowLeft size={14} />}
            disabled={selectedWeek <= 1}
            onClick={() => setSelectedWeek(prev => prev - 1)}
          >
            Prev Week
          </Button>
          <Button 
            variant="default" 
            size="compact-sm" 
            rightSection={<ArrowRight size={14} />}
            disabled={selectedWeek >= totalWeeks}
            onClick={() => setSelectedWeek(prev => prev + 1)}
          >
            Next Week
          </Button>
        </Group>
        <Group gap="xs">
          <Button 
            variant="light" 
            size="compact-sm" 
            leftSection={<Copy size={14} />}
            disabled={selectedWeek <= 1}
            onClick={() => handleCopySessions(selectedWeek - 1)}
          >
            Copy Previous
          </Button>
          <Button 
            variant="light" 
            size="compact-sm" 
            leftSection={<Copy size={14} />}
            disabled={selectedWeek >= totalWeeks}
            onClick={() => handleCopySessions(selectedWeek + 1)}
          >
            Copy Next
          </Button>
        </Group>
      </Group>

      {/* Planned Volume Graph */}
      {plannedMuscleVolume.length > 0 && (
        <Paper withBorder p="md">
          <Group gap="xs" mb="md">
            <BarChart3 size={18} />
            <Text fw={500}>Planned Weekly Volume (Sets)</Text>
          </Group>
          <Stack gap="xs">
            {(() => {
              const maxSets = Math.max(...plannedMuscleVolume.map(v => v.sets), 1)
              return plannedMuscleVolume.map((item, i) => (
                <Box key={i}>
                  <Group justify="space-between" mb={2}>
                    <Text size="xs" fw={500}>{item.label}</Text>
                    <Text size="xs" c="dimmed">{item.sets.toFixed(1)} sets</Text>
                  </Group>
                  <Progress 
                    value={(item.sets / maxSets) * 100} 
                    size="sm" 
                    color={item.label === 'Others' ? 'gray' : 'blue'}
                    radius="xl"
                  />
                </Box>
              ))
            })()}
          </Stack>
        </Paper>
      )}

      {/* Session cards */}
      {weekSessions.length > 0 ? (
        <SimpleGrid cols={{ base: 1, sm: 2, xl: 3 }} spacing="md">
          {weekSessions.map((session, i) => (
            <Paper
              key={`${session.date}-${i}`}
              withBorder
              p="md"
              style={{ cursor: 'pointer' }}
              onClick={() => openSessionEditor(session, session.date, i)}
            >
              <Group justify="space-between" mb="xs">
                <Text fw={500}>{session.day}</Text>
                <Badge variant="light" color={STATUS_COLORS[session.status ?? 'planned'] || 'blue'} size="sm">
                  {session.status || 'planned'}
                </Badge>
              </Group>
              <Text size="sm" c="dimmed" mb="sm">{session.date}</Text>

              {(session.planned_exercises || []).length > 0 ? (
                <Stack gap={4}>
                  {(() => {
                    const groups: Record<string, { sets: number; reps: number; kg: number | null }[]> = {}
                    for (const ex of session.planned_exercises!) {
                      if (!groups[ex.name]) groups[ex.name] = []
                      groups[ex.name].push(ex)
                    }
                    return Object.entries(groups).map(([name, items], j) => (
                      <Group key={j} justify="space-between" wrap="nowrap">
                        <Text size="sm" truncate style={{ flex: 1 }}>{name}</Text>
                        <Stack gap={0} align="flex-end">
                          {items.map((item, k) => (
                            <Text key={k} size="sm" c="dimmed">
                              {item.sets}x{item.reps}{item.kg !== null ? ` @${displayWeight(item.kg, unit)}` : ''}
                            </Text>
                          ))}
                        </Stack>
                      </Group>
                    ))
                  })()}
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">No exercises planned</Text>
              )}

              {session.exercises?.length > 0 && (
                <Text size="xs" c="dimmed" mt="sm" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }} pt="sm">
                  {session.exercises.length} exercises logged
                </Text>
              )}
            </Paper>
          ))}
        </SimpleGrid>
      ) : (
        <Group justify="center" py={48}>
          <Text c="dimmed">No sessions for Week {selectedWeek}. Click "Add Session" to plan one.</Text>
        </Group>
      )}

      {/* Session Editor Modal */}
      <Modal
        opened={isSessionEditorOpen}
        onClose={closeSessionEditor}
        title={editingSession ? 'Edit Session' : 'Plan Session'}
        size="lg"
      >
        <Stack gap="md">
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
            <DatePickerInput
              label="Date"
              value={sessionDate ? new Date(sessionDate) : null}
              onChange={(d) => {
                const date = d as Date | null
                if (date) {
                  setSessionDate(date.toISOString().slice(0, 10))
                } else {
                  setSessionDate(null)
                }
              }}
            />
            <Select
              label="Day"
              value={sessionDay}
              onChange={(v) => setSessionDay(v ?? 'Monday')}
              data={DAYS}
            />
          </SimpleGrid>

          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
            <TextInput
              label="Week"
              value={sessionWeek}
              onChange={(e) => setSessionWeek(e.currentTarget.value)}
            />
            <Select
              label="Phase"
              value={sessionPhase}
              onChange={(v) => setSessionPhase(v ?? '')}
              data={[
                { value: '', label: 'None' },
                ...phases.map(p => ({ value: p.name, label: p.name })),
              ]}
            />
          </SimpleGrid>

          {/* Planned exercises */}
          <Stack gap="xs">
            <Text size="sm" c="dimmed">Planned Exercises</Text>

            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={plannedExercises.map((ex) => ex.id)}
                strategy={verticalListSortingStrategy}
              >
                <Stack gap="xs">
                  {plannedExercises.map((ex) => (
                    <SortableExercise
                      key={ex.id}
                      ex={ex}
                      onRemove={removePlannedExercise}
                      onUpdate={updatePlannedExercise}
                    />
                  ))}
                </Stack>
              </SortableContext>
            </DndContext>

            {/* Add exercise */}
            <Autocomplete
              value={exerciseSearch}
              onChange={setExerciseSearch}
              data={autocompleteData}
              placeholder="Search exercises to add..."
              mt="sm"
              onOptionSubmit={(value) => {
                const match = glossary.find(e => e.name.toLowerCase() === value.toLowerCase())
                if (match) {
                  addPlannedExercise(match)
                } else {
                  // If no exact match in glossary, still add it as a custom exercise
                  setPlannedExercises(prev => [...prev, {
                    id: `ex-${Date.now()}-${prev.length}`,
                    name: value,
                    sets: 3,
                    reps: 5,
                    kg: null,
                  }])
                  setExerciseSearch('')
                }
              }}
            />
            {exerciseSearch && filteredGlossary.length > 0 && (
              <Stack gap={0} style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 'var(--mantine-radius-sm)', maxHeight: 160, overflowY: 'auto' }}>
                {filteredGlossary.map(ex => (
                  <Button
                    key={ex.id}
                    variant="subtle"
                    fullWidth
                    justify="flex-start"
                    size="sm"
                    onClick={() => addPlannedExercise(ex)}
                  >
                    {ex.name}
                  </Button>
                ))}
              </Stack>
            )}
            <Text size="xs" c="dimmed">Select an exercise from the dropdown to add it.</Text>
          </Stack>

          <Divider mt="md" />

          <Group justify="flex-end" gap="sm">
            <Button variant="default" onClick={closeSessionEditor}>
              Cancel
            </Button>
            <Button
              leftSection={<Save size={16} />}
              onClick={saveSession}
            >
              {editingSession ? 'Update' : 'Create'} Session
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Copy Confirmation Modal */}
      <Modal
        opened={isCopyModalOpen}
        onClose={() => setIsCopyModalOpen(false)}
        title={`Copy Sessions from Week ${copySourceWeek}`}
      >
        <Stack gap="md">
          <Text size="sm">
            You are about to copy all planned sessions from Week {copySourceWeek} to Week {selectedWeek}.
            Existing sessions in Week {selectedWeek} that fall on the same day will be handled based on your choice below.
            <Text fw={700} c="orange" mt="sm">Completed sessions will never be overwritten.</Text>
          </Text>

          <Select
            label="Collision Handling"
            value={copyCollisionMode}
            onChange={(v) => setCopyCollisionMode(v as 'overwrite' | 'add')}
            data={[
              { value: 'overwrite', label: 'Overwrite - Replace target day sets' },
              { value: 'add', label: 'Add - Keep existing and add new sets' },
            ]}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setIsCopyModalOpen(false)}>Cancel</Button>
            <Button color="blue" onClick={executeCopy}>Copy Sessions</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
