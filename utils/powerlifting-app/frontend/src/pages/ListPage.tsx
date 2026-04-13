import { useState, useMemo } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { groupSessionsByWeek, formatDateShort, getDayOfWeek } from '@/utils/dates'
import { displayWeight } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import SessionDrawer from '@/components/sessions/SessionDrawer'
import { Check, Dumbbell, Plus, Trash2 } from 'lucide-react'
import {
  Paper, Title, Text, Group, Stack, Button, ActionIcon, Badge,
  Select, Modal, Loader, Center, Box, Accordion,
} from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import type { Session } from '@powerlifting/types'

function parseDateString(ds: string): Date | null {
  if (!ds) return null
  const parts = ds.split('-')
  if (parts.length !== 3) return null
  return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
}

function toDateString(d: Date): string {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export default function ListPage() {
  const { program, isLoading, createSession, deleteSession } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()
  const [block, setBlock] = useState('current')

  const availableBlocks = useMemo(() => {
    if (!program) return ['current']
    const blocks = new Set<string>()
    for (const s of program.sessions) blocks.add(s.block ?? 'current')
    return Array.from(blocks).sort()
  }, [program])
  const [expandedWeeks, setExpandedWeeks] = useState<Set<number>>(new Set())
  const [drawerDate, setDrawerDate] = useState<string | null>(null)
  const [drawerArrayIndex, setDrawerArrayIndex] = useState<number | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newDate, setNewDate] = useState<string>('')

  // Get selected session
  const selectedSession = drawerDate
    ? program?.sessions.find((s) => s.date === drawerDate) || null
    : null
  const selectedSessionIndex = drawerDate
    ? program?.sessions.findIndex((s) => s.date === drawerDate) ?? -1
    : -1

  const handleAddSession = async () => {
    if (!newDate) {
      pushToast({ message: 'Please select a date', type: 'error' })
      return
    }

    try {
      const dayOfWeek = getDayOfWeek(newDate)
      await createSession({
        date: newDate,
        day: dayOfWeek,
        exercises: [],
      })
      pushToast({ message: 'Session created', type: 'success' })
      setShowAddModal(false)
      setNewDate('')
      // Open the new session in the drawer — find it by index after reload
      const newIndex = program?.sessions.findIndex(s => s.date === newDate) ?? -1
      setDrawerDate(newDate)
      setDrawerArrayIndex(newIndex >= 0 ? newIndex : null)
    } catch (err) {
      pushToast({ message: 'Failed to create session', type: 'error' })
    }
  }

  const handleDeleteSession = async (date: string, index: number) => {
    if (!confirm('Delete this session?')) return
    try {
      await deleteSession(date, index)
      pushToast({ message: 'Session deleted', type: 'success' })
      setDrawerDate(null)
      setDrawerArrayIndex(null)
    } catch (err) {
      pushToast({ message: 'Failed to delete session', type: 'error' })
    }
  }

  if (isLoading || !program) {
    return (
      <Center mih="50vh">
        <Loader />
      </Center>
    )
  }

  const sessionsByWeek = groupSessionsByWeek(program.sessions, block)

  const toggleWeek = (week: number) => {
    setExpandedWeeks((prev) => {
      const next = new Set(prev)
      if (next.has(week)) {
        next.delete(week)
      } else {
        next.add(week)
      }
      return next
    })
  }

  const handleSessionClick = (date: string, arrayIndex: number) => {
    setDrawerDate(date)
    setDrawerArrayIndex(arrayIndex)
  }

  return (
    <Stack gap="md" style={{ position: 'relative' }}>
      {/* Sticky header */}
      <Box
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          borderBottom: '1px solid var(--mantine-color-default-border)',
          paddingBottom: 8,
          marginBottom: 0,
        }}
      >
        <Group justify="space-between" wrap="nowrap">
          <Title order={2}>Sessions by Week</Title>
          <Group gap="xs" wrap="nowrap">
            {availableBlocks.length > 1 && (
              <Select
                value={block}
                onChange={(v) => setBlock(v || 'current')}
                data={availableBlocks.map((b) => ({
                  value: b,
                  label: b === 'current' ? 'Current Block' : b,
                }))}
                size="sm"
                style={{ width: 160 }}
              />
            )}
            <Button
              size="sm"
              leftSection={<Plus size={16} />}
              onClick={() => setShowAddModal(true)}
              visibleFrom="sm"
            >
              Add Session
            </Button>
          </Group>
        </Group>
      </Box>

      {/* Floating action button (mobile only) */}
      <ActionIcon
        size="xl"
        radius="xl"
        variant="filled"
        hiddenFrom="sm"
        onClick={() => setShowAddModal(true)}
        aria-label="Add Session"
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 40,
          width: 56,
          height: 56,
        }}
      >
        <Plus size={24} />
      </ActionIcon>

      {/* Add Session Modal */}
      <Modal
        opened={showAddModal}
        onClose={() => {
          setShowAddModal(false)
          setNewDate('')
        }}
        title="Add New Session"
        centered
      >
        <Stack gap="md">
          <Box>
            <Text size="sm" c="dimmed" mb={4}>Date</Text>
            <DatePickerInput
              value={newDate ? parseDateString(newDate) : null}
              valueFormat="YYYY-MM-DD"
              onChange={(d) => {
                if (d) setNewDate(toDateString(d))
                else setNewDate('')
              }}
            />
          </Box>
          <Group justify="flex-end" gap="xs">
            <Button
              variant="default"
              onClick={() => {
                setShowAddModal(false)
                setNewDate('')
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleAddSession}>
              Create Session
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Stack gap="xs">
        {Array.from(sessionsByWeek.entries()).map(([week, sessions]) => {
          const firstSession = sessions[0]
          const phase = firstSession?.phase
          const isExpanded = expandedWeeks.has(week)
          const completedCount = sessions.filter((s) => s.completed).length
          const phaseColorValue = phase ? phaseColor(phase, program.phases) : undefined

          return (
            <Paper key={week} withBorder>
              {/* Week Header */}
              <Box
                component="button"
                onClick={() => toggleWeek(week)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: 16,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <Text
                  fw={500}
                  style={{
                    transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                    transition: 'transform 150ms ease',
                    lineHeight: 1,
                  }}
                >
                  &#9662;
                </Text>

                {phase && (
                  <Box
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: '50%',
                      backgroundColor: phaseColorValue,
                      flexShrink: 0,
                    }}
                  />
                )}

                <Text fw={500}>Week {week}</Text>
                <Text size="sm" c="dimmed">
                  {phase?.name}
                </Text>

                <Box style={{ marginLeft: 'auto' }}>
                  <Text size="sm" c="dimmed">
                    {completedCount}/{sessions.length} completed
                  </Text>
                </Box>
              </Box>

              {/* Session List */}
              {isExpanded && (
                <Box
                  style={{
                    borderTop: '1px solid var(--mantine-color-default-border)',
                  }}
                >
                  {sessions.map((session, arrayIdx) => {
                    const previewExercises = session.exercises.length > 0 ? session.exercises : session.planned_exercises || []
                    const isPlanned = session.exercises.length === 0 && (session.planned_exercises?.length ?? 0) > 0
                    return (
                    <Box
                      key={`${session.date}-${arrayIdx}`}
                      component="button"
                      onClick={() => handleSessionClick(session.date, program.sessions.indexOf(session))}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        padding: 12,
                        background: 'none',
                        border: 'none',
                        borderBottom: '1px solid var(--mantine-color-default-border)',
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                      sx={(theme) => ({
                        '&:hover': {
                          backgroundColor: theme.colorScheme === 'dark'
                            ? 'rgba(255,255,255,0.03)'
                            : 'rgba(0,0,0,0.03)',
                        },
                        '&:last-child': {
                          borderBottom: 'none',
                        },
                      })}
                    >
                      <Box
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          backgroundColor: 'var(--mantine-color-default)',
                          flexShrink: 0,
                        }}
                      >
                        {session.completed ? (
                          <Check size={16} style={{ color: 'var(--mantine-color-primary-filled)' }} />
                        ) : (
                          <Dumbbell size={16} style={{ opacity: 0.6 }} />
                        )}
                      </Box>

                      <Box style={{ flex: 1 }}>
                        <Text fw={500}>{session.day}</Text>
                        <Text size="sm" c="dimmed">
                          {formatDateShort(session.date)}
                        </Text>
                      </Box>

                      <Box style={{ flex: 1, textAlign: 'right' }}>
                        <Text size="sm">
                          {session.exercises.length > 0
                            ? `${session.exercises.length} exercise${session.exercises.length !== 1 ? 's' : ''}`
                            : isPlanned
                              ? `${session.planned_exercises!.length} planned`
                              : 'No exercises'}
                        </Text>
                        {session.session_rpe !== null && (
                          <Text size="xs" c="dimmed">
                            RPE {session.session_rpe}
                          </Text>
                        )}
                      </Box>

                      {/* Quick exercise preview */}
                      <Box style={{ flex: 1, textAlign: 'right' }} visibleFrom="lg">
                        {previewExercises.slice(0, 3).map((ex, idx) => (
                          <Text key={idx} size="sm" c="dimmed" component="span">
                            {ex.name}
                            {ex.kg !== null && ` @ ${displayWeight(ex.kg, unit)}`}
                            {idx < Math.min(previewExercises.length, 3) - 1 && ', '}
                          </Text>
                        ))}
                        {previewExercises.length > 3 && (
                          <Text size="sm" c="dimmed" component="span">
                            {' '}+{previewExercises.length - 3} more
                          </Text>
                        )}
                      </Box>
                    </Box>
                    )
                  })}
                </Box>
              )}
            </Paper>
          )
        })}
      </Stack>

      {/* Session Drawer */}
      <SessionDrawer
        isOpen={drawerDate !== null}
        onClose={() => { setDrawerDate(null); setDrawerArrayIndex(null) }}
        session={selectedSession}
        sessionIndex={selectedSessionIndex}
        sessionArrayIndex={drawerArrayIndex ?? 0}
      />
    </Stack>
  )
}
