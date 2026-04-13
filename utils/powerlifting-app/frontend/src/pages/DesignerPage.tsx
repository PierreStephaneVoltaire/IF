import { useState, useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Trash2, X, Save } from 'lucide-react'
import {
  Stack, Group, Text, Button, Paper, Badge, Modal, SimpleGrid,
  TextInput, NumberInput, Select, ActionIcon, Autocomplete,
} from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import * as api from '@/api/client'
import type { Session, PlannedExercise, GlossaryExercise } from '@powerlifting/types'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const STATUS_COLORS: Record<string, string> = {
  planned: 'blue',
  completed: 'green',
  logged: 'yellow',
  skipped: 'gray',
}

export default function DesignerPage() {
  const { program, version, createSession } = useProgramStore()
  const { pushToast } = useUiStore()
  const [searchParams] = useSearchParams()

  const [block, setBlock] = useState('current')
  const [selectedWeek, setSelectedWeek] = useState(1)
  const [editingSession, setEditingSession] = useState<Session | null>(null)
  const [editingSessionGlobalIndex, setEditingSessionGlobalIndex] = useState<number>(-1)
  const [editingSessionDate, setEditingSessionDate] = useState<string>('')
  const [isSessionEditorOpen, setIsSessionEditorOpen] = useState(false)
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [exerciseSearch, setExerciseSearch] = useState('')

  // Session form state
  const [sessionDate, setSessionDate] = useState<string | null>(null)
  const [sessionDay, setSessionDay] = useState('Monday')
  const [sessionWeek, setSessionWeek] = useState('W1')
  const [sessionPhase, setSessionPhase] = useState('')
  const [plannedExercises, setPlannedExercises] = useState<PlannedExercise[]>([])

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
      setPlannedExercises(session.planned_exercises || [])
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

      const sessionData: Partial<Session> & { date: string } = {
        date: dateStr,
        day: sessionDay,
        week: sessionWeek,
        status: 'planned',
        completed: false,
        planned_exercises: plannedExercises,
        exercises: [],
        session_notes: '',
      }

      if (editingSession) {
        if (editingSessionGlobalIndex < 0) {
          throw new Error('Could not resolve the session index for update')
        }
        await api.updatePlannedExercises(version, editingSessionDate, editingSessionGlobalIndex, plannedExercises)
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
      name: exercise.name,
      sets: 3,
      reps: 5,
      kg: null,
    }])
    setExerciseSearch('')
  }

  function updatePlannedExercise(index: number, field: keyof PlannedExercise, value: unknown) {
    setPlannedExercises(prev => prev.map((pe, i) => i === index ? { ...pe, [field]: value } : pe))
  }

  function removePlannedExercise(index: number) {
    setPlannedExercises(prev => prev.filter((_, i) => i !== index))
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
                  {session.planned_exercises!.map((ex, j) => (
                    <Group key={j} justify="space-between">
                      <Text size="sm">{ex.name}</Text>
                      <Text size="sm" c="dimmed">
                        {ex.sets}x{ex.reps}{ex.kg ? ` @${ex.kg}kg` : ''}
                      </Text>
                    </Group>
                  ))}
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
              value={sessionDate}
              onChange={setSessionDate}
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

            {plannedExercises.map((ex, i) => (
              <Paper key={i} withBorder p="xs" radius="sm">
                <Group justify="space-between" gap="xs" mb={4}>
                  <Text size="sm" fw={500} truncate>{ex.name}</Text>
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    size="sm"
                    onClick={() => removePlannedExercise(i)}
                  >
                    <Trash2 size={12} />
                  </ActionIcon>
                </Group>
                <Group gap={6}>
                  <NumberInput
                    value={ex.sets}
                    onChange={(v) => updatePlannedExercise(i, 'sets', v)}
                    min={0}
                    w={60}
                    placeholder="Sets"
                  />
                  <Text size="xs" c="dimmed">x</Text>
                  <NumberInput
                    value={ex.reps}
                    onChange={(v) => updatePlannedExercise(i, 'reps', v)}
                    min={0}
                    w={60}
                    placeholder="Reps"
                  />
                  <Text size="xs" c="dimmed">@</Text>
                  <NumberInput
                    value={ex.kg ?? undefined}
                    onChange={(v) => updatePlannedExercise(i, 'kg', v ?? null)}
                    min={0}
                    w={70}
                    placeholder="kg"
                  />
                </Group>
              </Paper>
            ))}

            {/* Add exercise */}
            <Autocomplete
              value={exerciseSearch}
              onChange={setExerciseSearch}
              data={autocompleteData}
              placeholder="Search exercises to add..."
              mt="sm"
              onOptionSubmit={(value) => {
                const match = filteredGlossary.find(e => e.name === value)
                if (match) addPlannedExercise(match)
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
    </Stack>
  )
}
