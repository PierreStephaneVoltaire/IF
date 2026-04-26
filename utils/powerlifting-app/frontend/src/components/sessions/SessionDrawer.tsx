import { useState, useEffect, useMemo, Fragment } from 'react'
import { Drawer, Button, Group, Stack, Paper, SimpleGrid, NumberInput, Textarea, Autocomplete, ActionIcon, Text, Box, Table, Divider, SegmentedControl, Slider, Modal } from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { getDayOfWeek } from '@/utils/dates'
import { displayWeight, toDisplayUnit, fromDisplayUnit } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import { fetchGlossary } from '@/api/client'
import { X, Check, Save, RotateCcw, Plus, GripVertical, Trash2, Calendar, Film, HeartPulse, ArrowLeft, Calculator } from 'lucide-react'
import type { Session, Exercise, SessionVideo, SessionWellness, GlossaryExercise } from '@powerlifting/types'
import VideoGrid from './VideoGrid'
import VideoUploadModal from './VideoUploadModal'
import SessionToolkitModal from './SessionToolkitModal'
import { normalizeExerciseName } from '@/utils/volume'

const WELLNESS_FIELDS: Array<{
  key: keyof Omit<SessionWellness, 'recorded_at'>
  label: string
}> = [
  { key: 'sleep', label: 'Sleep' },
  { key: 'soreness', label: 'Soreness' },
  { key: 'mood', label: 'Mood' },
  { key: 'stress', label: 'Stress' },
  { key: 'energy', label: 'Energy' },
]

function clampWellnessScore(value: number): 1 | 2 | 3 | 4 | 5 {
  return Math.max(1, Math.min(5, Math.round(value))) as 1 | 2 | 3 | 4 | 5
}

function createDefaultWellness(existing?: SessionWellness | null): SessionWellness {
  return {
    sleep: clampWellnessScore(existing?.sleep ?? 3),
    soreness: clampWellnessScore(existing?.soreness ?? 3),
    mood: clampWellnessScore(existing?.mood ?? 3),
    stress: clampWellnessScore(existing?.stress ?? 3),
    energy: clampWellnessScore(existing?.energy ?? 3),
    recorded_at: existing?.recorded_at ?? new Date().toISOString(),
  }
}

interface SessionDrawerProps {
  isOpen: boolean
  onClose: () => void
  session: Session | null
  sessionIndex: number
  sessionArrayIndex: number
  mode?: 'drawer' | 'page'
  onSaveSuccess?: () => void
  onDeleteSuccess?: () => void
}

export default function SessionDrawer({
  isOpen,
  onClose,
  session,
  sessionArrayIndex,
  mode = 'drawer',
  onSaveSuccess,
}: SessionDrawerProps) {
  const { program, updateSession, saveSession, rescheduleSession } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()
  const [localSession, setLocalSession] = useState<Session | null>(null)
  const [originalDate, setOriginalDate] = useState<string>('')
  const [hasChanges, setHasChanges] = useState(false)
  const [showVideoUpload, setShowVideoUpload] = useState(false)
  const [discardIntent, setDiscardIntent] = useState<'reset' | 'close' | null>(null)
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [toolkitExercise, setToolkitExercise] = useState<{
    name: string
    targetKg: number | null
    reps: number | null
    isBarbell: boolean
  } | null>(null)

  useEffect(() => {
    fetchGlossary()
      .then((exercises) => setGlossary(exercises))
      .catch(() => {})
  }, [])

  const glossaryNames = useMemo(() => glossary.map((e) => e.name).sort(), [glossary])
  const glossaryLookup = useMemo(() => {
    const lookup = new Map<string, GlossaryExercise>()
    for (const exercise of glossary) {
      lookup.set(normalizeExerciseName(exercise.name), exercise)
    }
    return lookup
  }, [glossary])

  // Initialize local state when session changes
  useEffect(() => {
    if (session) {
      const clone = JSON.parse(JSON.stringify(session)) as Session
      // Pre-populate exercises from planned_exercises for incomplete sessions
      if (!clone.completed && clone.exercises.length === 0 && (clone.planned_exercises?.length ?? 0) > 0) {
        clone.exercises = clone.planned_exercises!.map(pe => ({
          name: pe.name,
          sets: pe.sets,
          reps: pe.reps,
          kg: pe.kg,
          notes: '',
          failed_sets: Array(pe.sets).fill(false),
        }))
      }
      // Ensure failed_sets exists on all exercises
      for (const ex of clone.exercises) {
        if (!ex.failed_sets) {
          ex.failed_sets = Array(ex.sets).fill(false)
        }
      }
      setLocalSession(clone)
      setOriginalDate(session.date)
      setHasChanges(false)
    }
  }, [session])

  const phaseColorValue = session && program ? phaseColor(session.phase, program.phases) : 'var(--mantine-color-gray-6)'

  if (!session || !localSession || !program) return null
  const wellness = localSession.wellness

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
      setOriginalDate(localSession.date)
      pushToast({ message: 'Session saved successfully', type: 'success' })
      if (onSaveSuccess) {
        onSaveSuccess()
      } else if (mode === 'drawer') {
        onClose()
      }
    } catch (err) {
      console.error(err)
      pushToast({ message: 'Failed to save session', type: 'error' })
    }
  }

  const handleDiscard = () => {
    setLocalSession(JSON.parse(JSON.stringify(session)))
    setHasChanges(false)
  }

  const confirmDiscard = () => {
    if (discardIntent === 'reset') {
      handleDiscard()
    } else if (discardIntent === 'close') {
      handleDiscard()
      onClose()
    }
    setDiscardIntent(null)
  }

  const handleCloseWithCheck = () => {
    if (hasChanges) {
      setDiscardIntent('close')
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
          { name: '', sets: 3, reps: 5, kg: null, notes: '', failed_sets: [false, false, false] },
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

  const toggleFailedSet = (exerciseIndex: number, setIndex: number) => {
    setLocalSession((prev) => {
      if (!prev) return prev
      const exercises = prev.exercises.map((ex, i) => {
        if (i !== exerciseIndex) return ex
        const failed = [...(ex.failed_sets || Array(ex.sets).fill(false))]
        failed[setIndex] = !failed[setIndex]
        return { ...ex, failed_sets: failed }
      })
      return { ...prev, exercises }
    })
    setHasChanges(true)
  }

  const updateSetsWithResize = (index: number, newSets: number) => {
    setLocalSession((prev) => {
      if (!prev) return prev
      const exercises = prev.exercises.map((ex, i) => {
        if (i !== index) return ex
        let failed = ex.failed_sets || Array(ex.sets).fill(false)
        if (failed.length < newSets) {
          failed = [...failed, ...Array(newSets - failed.length).fill(false)]
        } else if (failed.length > newSets) {
          failed = failed.slice(0, newSets)
        }
        return { ...ex, sets: newSets, failed_sets: failed }
      })
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

  const setWellnessMode = (enabled: boolean) => {
    setLocalSession((prev) => {
      if (!prev) return prev
      if (!enabled) {
        const next = { ...prev }
        delete next.wellness
        return next
      }
      return { ...prev, wellness: createDefaultWellness(prev.wellness) }
    })
    setHasChanges(true)
  }

  const updateWellness = (field: keyof Omit<SessionWellness, 'recorded_at'>, value: number) => {
    setLocalSession((prev) => {
      if (!prev) return prev
      const current = prev.wellness ?? createDefaultWellness()
      return {
        ...prev,
        wellness: {
          ...current,
          [field]: clampWellnessScore(value),
          recorded_at: new Date().toISOString(),
        },
      }
    })
    setHasChanges(true)
  }

  const openToolkitForExercise = (exercise: Exercise) => {
    const match = glossaryLookup.get(normalizeExerciseName(exercise.name))
    setToolkitExercise({
      name: exercise.name,
      targetKg: exercise.kg,
      reps: exercise.reps,
      isBarbell: match ? ['barbell', 'hex_bar'].includes(match.equipment) : true,
    })
  }

  const editorContent = (
      <Stack
        gap="lg"
        pb={mode === 'page' ? 'calc(120px + env(safe-area-inset-bottom, 0px))' : undefined}
      >
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <Group gap="sm" align="flex-start">
            <Box
              w={12}
              h={12}
              mt={6}
              style={{ borderRadius: '50%', backgroundColor: phaseColorValue }}
            />
            <Box>
              <Group gap="xs" align="center">
                <Calendar size={16} style={{ opacity: 0.6 }} />
                <DatePickerInput
                  value={localSession.date}
                  valueFormat="YYYY-MM-DD"
                  onChange={(d) => {
                    if (d) updateDate(d as string)
                  }}
                  size="sm"
                  style={{ width: 'auto' }}
                />
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                {localSession.day}
                {localSession.phase?.name ? ` • ${localSession.phase.name}` : ''}
              </Text>
            </Box>
          </Group>
          <ActionIcon variant="subtle" onClick={handleCloseWithCheck} size="lg" title={mode === 'page' ? 'Back' : 'Close'}>
            {mode === 'page' ? <ArrowLeft size={20} /> : <X size={20} />}
          </ActionIcon>
        </Group>

        <Paper withBorder p="md" radius="md">
          <Group justify="space-between" align="center" mb="sm">
            <Group gap="xs">
              <HeartPulse size={16} />
              <Text size="sm" fw={600}>Subjective Wellness</Text>
            </Group>
            <SegmentedControl
              size="xs"
              value={localSession.wellness ? 'record' : 'skip'}
              onChange={(value) => setWellnessMode(value === 'record')}
              data={[
                { label: 'Skip', value: 'skip' },
                { label: 'Record', value: 'record' },
              ]}
            />
          </Group>

          {wellness ? (
            <Stack gap="sm">
              {WELLNESS_FIELDS.map((field) => (
                <Box key={field.key}>
                  <Group justify="space-between" mb={4}>
                    <Text size="xs" c="dimmed">{field.label}</Text>
                    <Text size="xs" fw={500}>{wellness[field.key] ?? 3}/5</Text>
                  </Group>
                  <Slider
                    value={wellness[field.key]}
                    onChange={(value) => updateWellness(field.key, value)}
                    min={1}
                    max={5}
                    step={1}
                    marks={[
                      { value: 1, label: '1' },
                      { value: 2, label: '2' },
                      { value: 3, label: '3' },
                      { value: 4, label: '4' },
                      { value: 5, label: '5' },
                    ]}
                    color={field.key === 'soreness' || field.key === 'stress' ? 'orange' : 'blue'}
                  />
                </Box>
              ))}
              <Text size="xs" c="dimmed">
                Higher scores are better. Soreness and stress are inverted in readiness math.
              </Text>
            </Stack>
          ) : (
            <Text size="xs" c="dimmed">No wellness captured for this session.</Text>
          )}
        </Paper>

        <Paper withBorder p="md" radius="md">
          <Group justify="space-between" align="center" mb="md">
            <Text size="sm" fw={600}>Workout</Text>
            <Button
              variant="dashed"
              onClick={addExercise}
              leftSection={<Plus size={16} />}
            >
              Add Exercise
            </Button>
          </Group>

          <Stack gap="sm">
          {/* Planned exercises reference */}
          {(localSession.planned_exercises?.length ?? 0) > 0 && (
            <Paper bg="var(--mantine-color-default)" p="xs" radius="md">
              <Text size="xs" c="dimmed" fw={500} mb={4}>Planned</Text>
              <Group gap="md" wrap="wrap">
                {localSession.planned_exercises!.map((pe, i) => (
                  <Text key={i} size="xs" c="dimmed" span>
                    {pe.name} {pe.sets}x{pe.reps}{pe.kg !== null ? ` @${toDisplayUnit(pe.kg, unit)}${unit}` : ''}
                  </Text>
                ))}
              </Group>
            </Paper>
          )}
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
              <Paper key={group.name || `ungrouped-${groupIdx}`} withBorder p="sm" radius="md">
                <Group gap="xs" mb="xs">
                  <GripVertical size={16} style={{ cursor: 'move', opacity: 0.5 }} />
                  <Autocomplete
                    value={group.name}
                    onChange={(newName) => {
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
                    data={glossaryNames}
                    placeholder="Exercise name"
                    size="sm"
                    style={{ flex: 1 }}
                  />
                  {group.entries.length === 1 && (
                    <Group gap={4} wrap="nowrap">
                      <ActionIcon
                        variant="subtle"
                        color="blue"
                        onClick={() => openToolkitForExercise(group.entries[0].exercise)}
                        title="Open toolkit"
                      >
                        <Calculator size={16} />
                      </ActionIcon>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        onClick={() => removeExercise(group.entries[0].originalIndex)}
                      >
                        <Trash2 size={16} />
                      </ActionIcon>
                    </Group>
                  )}
                </Group>
                {group.entries.length > 1 ? (
                  <Box style={{ overflowX: 'auto' }}>
                    <Table fz="sm" mb={4} style={{ minWidth: 360 }}>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th w={80}>Sets</Table.Th>
                          <Table.Th w={80}>Reps</Table.Th>
                          <Table.Th w={96}>{unit}</Table.Th>
                          <Table.Th w={120} visibleFrom="sm">Failed Set</Table.Th>
                          <Table.Th w={40} />
                          <Table.Th w={40} />
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {group.entries.map((entry) => (
                          <Fragment key={entry.originalIndex}>
                            <Table.Tr>
                              <Table.Td>
                                <NumberInput
                                  value={entry.exercise.sets || ''}
                                  onChange={(v) => updateSetsWithResize(entry.originalIndex, Number(v) || 0)}
                                  size="sm"
                                  min={0}
                                />
                              </Table.Td>
                              <Table.Td>
                                <NumberInput
                                  value={entry.exercise.reps || ''}
                                  onChange={(v) => updateExercise(entry.originalIndex, 'reps', Number(v) || 0)}
                                  size="sm"
                                  min={0}
                                />
                              </Table.Td>
                              <Table.Td>
                                <NumberInput
                                  value={entry.exercise.kg !== null && entry.exercise.kg !== undefined ? toDisplayUnit(entry.exercise.kg, unit) : ''}
                                  onChange={(v) => updateExercise(entry.originalIndex, 'kg', v !== '' ? fromDisplayUnit(Number(v), unit) : null)}
                                  size="sm"
                                  decimalScale={2}
                                />
                              </Table.Td>
                              <Table.Td visibleFrom="sm">
                                <Group gap={4}>
                                  {(entry.exercise.failed_sets || []).map((f, si) => (
                                    <ActionIcon
                                      key={si}
                                      size="sm"
                                      variant={f ? 'filled' : 'default'}
                                      color={f ? 'red' : 'gray'}
                                      onClick={() => toggleFailedSet(entry.originalIndex, si)}
                                      title={`Set ${si + 1}${f ? ' (failed)' : ''}`}
                                    >
                                      <Text fz={10}>{si + 1}</Text>
                                    </ActionIcon>
                                  ))}
                                </Group>
                              </Table.Td>
                              <Table.Td>
                                <ActionIcon
                                  variant="subtle"
                                  color="blue"
                                  size="sm"
                                  onClick={() => openToolkitForExercise(entry.exercise)}
                                  title="Open toolkit"
                                >
                                  <Calculator size={14} />
                                </ActionIcon>
                              </Table.Td>
                              <Table.Td>
                                <ActionIcon
                                  variant="subtle"
                                  color="red"
                                  size="sm"
                                  onClick={() => removeExercise(entry.originalIndex)}
                                >
                                  <Trash2 size={14} />
                                </ActionIcon>
                              </Table.Td>
                            </Table.Tr>
                            <Table.Tr>
                              <Table.Td colSpan={6} pt={4} pb={12} style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}>
                                {(entry.exercise.failed_sets || []).length > 0 && (
                                  <Box hiddenFrom="sm" mb="xs">
                                    <Group gap="xs">
                                      <Text size="xs" c="dimmed">Failed Set:</Text>
                                      <Group gap={4}>
                                        {(entry.exercise.failed_sets || []).map((f, si) => (
                                          <ActionIcon
                                            key={si}
                                            size="xs"
                                            variant={f ? 'filled' : 'default'}
                                            color={f ? 'red' : 'gray'}
                                            onClick={() => toggleFailedSet(entry.originalIndex, si)}
                                            title={`Set ${si + 1}${f ? ' (failed)' : ''}`}
                                          >
                                            <Text fz={9}>{si + 1}</Text>
                                          </ActionIcon>
                                        ))}
                                      </Group>
                                    </Group>
                                  </Box>
                                )}
                                <Textarea
                                  value={entry.exercise.notes || ''}
                                  onChange={(e) => updateExercise(entry.originalIndex, 'notes', e.currentTarget.value)}
                                  placeholder="Exercise notes..."
                                  size="sm"
                                  autosize
                                  minRows={1}
                                  maxRows={mode === 'page' ? 3 : 4}
                                  variant="filled"
                                  style={{ width: '100%' }}
                                />
                              </Table.Td>
                            </Table.Tr>
                          </Fragment>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Box>
                ) : (
                  <Box>
                    <Group justify="space-between" align="flex-start" mb="xs" wrap="nowrap">
                      <SimpleGrid cols={{ base: 3, sm: 3 }} spacing="xs" style={{ flex: 1 }}>
                      <Box>
                        <Text size="xs" c="dimmed">Sets</Text>
                        <NumberInput
                          value={group.entries[0].exercise.sets || ''}
                          onChange={(v) => updateSetsWithResize(group.entries[0].originalIndex, Number(v) || 0)}
                          size="sm"
                          min={0}
                        />
                      </Box>
                      <Box>
                        <Text size="xs" c="dimmed">Reps</Text>
                        <NumberInput
                          value={group.entries[0].exercise.reps || ''}
                          onChange={(v) => updateExercise(group.entries[0].originalIndex, 'reps', Number(v) || 0)}
                          size="sm"
                          min={0}
                        />
                      </Box>
                      <Box>
                        <Text size="xs" c="dimmed">{unit}</Text>
                        <NumberInput
                          value={group.entries[0].exercise.kg !== null && group.entries[0].exercise.kg !== undefined ? toDisplayUnit(group.entries[0].exercise.kg, unit) : ''}
                          onChange={(v) => updateExercise(group.entries[0].originalIndex, 'kg', v !== '' ? fromDisplayUnit(Number(v), unit) : null)}
                          size="sm"
                          decimalScale={2}
                        />
                      </Box>
                      </SimpleGrid>
                      <ActionIcon
                        variant="subtle"
                        color="blue"
                        onClick={() => openToolkitForExercise(group.entries[0].exercise)}
                        title="Open toolkit"
                      >
                        <Calculator size={16} />
                      </ActionIcon>
                    </Group>
                    
                    <Box mt="xs">
                      <Text size="xs" c="dimmed">Notes</Text>
                      <Textarea
                        value={group.entries[0].exercise.notes || ''}
                        onChange={(e) => updateExercise(group.entries[0].originalIndex, 'notes', e.currentTarget.value)}
                        placeholder="Exercise notes..."
                        size="sm"
                        autosize
                        minRows={1}
                        maxRows={mode === 'page' ? 3 : 4}
                        variant="filled"
                      />
                    </Box>

                    {(group.entries[0].exercise.failed_sets || []).length > 0 && (
                      <Group gap="xs" mt={6}>
                        <Text size="xs" c="dimmed">Failed Set:</Text>
                        <Group gap={4}>
                          {(group.entries[0].exercise.failed_sets || []).map((f, si) => (
                            <ActionIcon
                              key={si}
                              size="xs"
                              variant={f ? 'filled' : 'default'}
                              color={f ? 'red' : 'gray'}
                              onClick={() => toggleFailedSet(group.entries[0].originalIndex, si)}
                              title={`Set ${si + 1}${f ? ' (failed)' : ''}`}
                            >
                              <Text fz={9}>{si + 1}</Text>
                            </ActionIcon>
                          ))}
                        </Group>
                      </Group>
                    )}
                  </Box>
                )}
              </Paper>
            ))
          })()}

          {/* Videos Section */}
          <Divider my="sm" />
          <Group justify="space-between" mb="sm">
            <Group gap="xs">
              <Film size={16} />
              <Text size="sm" fw={500}>Videos</Text>
              {(session.videos?.length || 0) > 0 && (
                <Text size="xs" c="dimmed" span>({session.videos?.length})</Text>
              )}
            </Group>
            <Button
              size="xs"
              variant="default"
              onClick={() => setShowVideoUpload(true)}
              leftSection={<Plus size={12} />}
            >
              Upload
            </Button>
          </Group>

          {session.videos && session.videos.length > 0 ? (
            <VideoGrid session={session} />
          ) : (
            <Text size="xs" c="dimmed" ta="center" py="md">
              No videos uploaded for this session
            </Text>
          )}
          </Stack>
        </Paper>

        <Paper withBorder p="md" radius="md">
          <Stack gap="sm">
            <Text size="sm" fw={600}>Session Summary</Text>
          <SimpleGrid cols={2} spacing="sm">
            <Box>
              <Text size="xs" c="dimmed">Session RPE</Text>
              <NumberInput
                value={localSession.session_rpe || ''}
                onChange={(v) => updateRpe(Number(v) || null)}
                placeholder="1-10"
                size="sm"
                min={1}
                max={10}
                step={0.5}
              />
            </Box>
            <Box>
              <Text size="xs" c="dimmed">Body Weight ({unit})</Text>
              <NumberInput
                value={
                  localSession.body_weight_kg
                    ? toDisplayUnit(localSession.body_weight_kg, unit)
                    : ''
                }
                onChange={(v) => updateBodyWeight(v !== '' ? fromDisplayUnit(Number(v), unit) : null)}
                placeholder={unit}
                size="sm"
                step={0.1}
                decimalScale={1}
              />
            </Box>
          </SimpleGrid>

          <Box>
            <Text size="xs" c="dimmed">Session Notes</Text>
            <Textarea
              value={localSession.session_notes || ''}
              onChange={(e) => updateNotes(e.currentTarget.value)}
              placeholder="How did the session feel?"
              autosize
              minRows={1}
              maxRows={mode === 'page' ? 4 : 6}
              size="sm"
            />
          </Box>
          </Stack>
        </Paper>

        <Group justify="flex-end" wrap="wrap">
          <Button
            variant="default"
            color="gray"
            onClick={() => setDiscardIntent('reset')}
            disabled={!hasChanges}
            leftSection={<RotateCcw size={16} />}
          >
            Discard
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasChanges}
            leftSection={<Save size={16} />}
          >
            Save
          </Button>
          <Button
            variant={localSession.completed ? 'filled' : 'default'}
            onClick={toggleComplete}
            leftSection={<Check size={16} />}
          >
            {localSession.completed ? 'Done' : 'Mark Done'}
          </Button>
        </Group>
      </Stack>
  )

  return (
    <>
      {mode === 'drawer' ? (
        <Drawer
          opened={isOpen}
          onClose={handleCloseWithCheck}
          position="right"
          size="xl"
          withCloseButton={false}
          overlayProps={{ backgroundOpacity: 0.25 }}
        >
          {editorContent}
        </Drawer>
      ) : (
        <Box>
          {editorContent}
        </Box>
      )}

      <Modal
        opened={discardIntent !== null}
        onClose={() => setDiscardIntent(null)}
        title="Discard changes?"
        centered
      >
        <Stack gap="md">
          <Text size="sm">
            {discardIntent === 'close'
              ? 'You have unsaved changes. Discard them and leave this page?'
              : 'Discard all unsaved changes to this session?'}
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDiscardIntent(null)}>Cancel</Button>
            <Button color="red" onClick={confirmDiscard}>Discard</Button>
          </Group>
        </Stack>
      </Modal>

      {/* Video Upload Modal */}
      <VideoUploadModal
        session={session}
        isOpen={showVideoUpload}
        onClose={() => setShowVideoUpload(false)}
        onUploaded={(video: SessionVideo) => {
          // Update local state and the store for persistence
          setLocalSession((prev) => {
            if (!prev) return prev
            const updated = {
              ...prev,
              videos: [...(prev.videos || []), video],
            }
            // Update store so it's not lost on navigation
            updateSession(prev.date, sessionArrayIndex, updated)
            return updated
          })
          setShowVideoUpload(false)
        }}
      />

      <SessionToolkitModal
        opened={toolkitExercise !== null}
        onClose={() => setToolkitExercise(null)}
        exerciseName={toolkitExercise?.name || ''}
        targetKg={toolkitExercise?.targetKg ?? null}
        reps={toolkitExercise?.reps ?? null}
        isBarbell={toolkitExercise?.isBarbell ?? true}
      />
    </>
  )
}
