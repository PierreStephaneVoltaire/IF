import { useState, useEffect, useMemo } from 'react'
import { Drawer, Button, Group, Stack, Paper, SimpleGrid, TextInput, NumberInput, Textarea, Autocomplete, ActionIcon, Text, Box, Table, Divider } from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { formatDateLong, getDayOfWeek } from '@/utils/dates'
import { displayWeight, toDisplayUnit, fromDisplayUnit } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import { fetchGlossary } from '@/api/client'
import { X, Check, Save, RotateCcw, Plus, GripVertical, Trash2, Calendar, Film, Loader2 } from 'lucide-react'
import type { Session, Exercise, SessionVideo } from '@powerlifting/types'
import VideoGrid from './VideoGrid'
import VideoUploadModal from './VideoUploadModal'

interface SessionDrawerProps {
  isOpen: boolean
  onClose: () => void
  session: Session | null
  sessionIndex: number
  sessionArrayIndex: number
}

export default function SessionDrawer({
  isOpen,
  onClose,
  session,
  sessionIndex,
  sessionArrayIndex,
}: SessionDrawerProps) {
  const { program, updateSession, saveSession, rescheduleSession, deleteSession } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()

  const [localSession, setLocalSession] = useState<Session | null>(null)
  const [originalDate, setOriginalDate] = useState<string>('')
  const [hasChanges, setHasChanges] = useState(false)
  const [showVideoUpload, setShowVideoUpload] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [glossaryNames, setGlossaryNames] = useState<string[]>([])

  useEffect(() => {
    fetchGlossary()
      .then((exercises) => setGlossaryNames(exercises.map((e) => e.name).sort()))
      .catch(() => {})
  }, [])

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

  if (!session || !localSession || !program) return null

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

  const handleDelete = async () => {
    if (!confirm('Delete this entire session? This cannot be undone.')) return
    setIsDeleting(true)
    try {
      await deleteSession(originalDate, sessionArrayIndex)
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

  // Helper to parse date string "YYYY-MM-DD" to Date
  const parseDateString = (ds: string): Date | null => {
    if (!ds) return null
    const parts = ds.split('-')
    if (parts.length !== 3) return null
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
  }

  return (
    <>
      <Drawer
        opened={isOpen}
        onClose={handleCloseWithCheck}
        position="right"
        size={{ base: '100%', sm: 'xl' }}
        withCloseButton={false}
        overlayProps={{ backgroundOpacity: 0.25 }}
      >
        {/* Header */}
        <Box>
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Group gap="sm" align="flex-start">
              <Box
                w={12}
                h={12}
                mt={4}
                style={{ borderRadius: '50%', backgroundColor: phaseColorValue }}
              />
              <Box>
                <Text fw={500}>{localSession.week}</Text>
                <Group gap="xs">
                  <Calendar size={16} style={{ opacity: 0.6 }} />
                  <DatePickerInput
                    value={localSession.date}
                    valueFormat="YYYY-MM-DD"
                    onChange={(d) => {
                      if (d) updateDate(d as string)
                    }}
                    size="xs"
                    style={{ width: 'auto' }}
                  />
                  <Text size="xs" c="dimmed">{localSession.day}</Text>
                </Group>
              </Box>
            </Group>
            <Group gap="xs">
              <Button
                variant={localSession.completed ? 'filled' : 'default'}
                size="xs"
                onClick={toggleComplete}
                leftSection={localSession.completed ? <Check size={16} /> : undefined}
              >
                {localSession.completed ? 'Done' : 'Mark Done'}
              </Button>
              <ActionIcon variant="subtle" onClick={handleCloseWithCheck} size="lg">
                <X size={20} />
              </ActionIcon>
            </Group>
          </Group>
        </Box>

        <Divider my="sm" />

        {/* Exercises */}
        <Stack gap="sm" style={{ flex: 1, overflowY: 'auto' }}>
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
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => removeExercise(group.entries[0].originalIndex)}
                    >
                      <Trash2 size={16} />
                    </ActionIcon>
                  )}
                </Group>
                {group.entries.length > 1 ? (
                  <Box style={{ overflowX: 'auto' }}>
                    <Table fz="sm" mb={4} style={{ minWidth: 480 }}>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th w={80}>Sets</Table.Th>
                          <Table.Th w={80}>Reps</Table.Th>
                          <Table.Th w={96}>{unit}</Table.Th>
                          <Table.Th w={120}>Failed Set</Table.Th>
                          <Table.Th>Notes</Table.Th>
                          <Table.Th w={40} />
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {group.entries.map((entry) => (
                          <Table.Tr key={entry.originalIndex}>
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
                            <Table.Td>
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
                              <TextInput
                                value={entry.exercise.notes || ''}
                                onChange={(e) => updateExercise(entry.originalIndex, 'notes', e.currentTarget.value)}
                                placeholder="Notes"
                                size="sm"
                              />
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
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Box>
                ) : (
                  <Box>
                    <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
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
                      <Box>
                        <Text size="xs" c="dimmed">Notes</Text>
                        <TextInput
                          value={group.entries[0].exercise.notes || ''}
                          onChange={(e) => updateExercise(group.entries[0].originalIndex, 'notes', e.currentTarget.value)}
                          placeholder="Notes"
                          size="sm"
                        />
                      </Box>
                    </SimpleGrid>
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

          <Button
            variant="dashed"
            fullWidth
            onClick={addExercise}
            leftSection={<Plus size={16} />}
          >
            Add Exercise
          </Button>

          {/* Videos Section */}
          <Divider my="md" />
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

        <Divider my="sm" />

        {/* Footer */}
        <Stack gap="sm">
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
              minRows={2}
              size="sm"
            />
          </Box>

          {/* Actions */}
          <Group>
            <ActionIcon
              variant="subtle"
              color="red"
              onClick={handleDelete}
              disabled={isDeleting}
              size="lg"
            >
              {isDeleting ? <Loader2 className="animate-spin" size={16} /> : <Trash2 size={16} />}
            </ActionIcon>
            <Button
              variant="default"
              onClick={handleDiscard}
              disabled={!hasChanges}
              leftSection={<RotateCcw size={16} />}
              style={{ flex: 1 }}
            >
              Discard
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasChanges}
              leftSection={<Save size={16} />}
              style={{ flex: 1 }}
            >
              Save
            </Button>
          </Group>
        </Stack>
      </Drawer>

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
    </>
  )
}
