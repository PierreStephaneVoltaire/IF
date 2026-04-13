import { useEffect, useMemo, useState } from 'react'
import {
  Group,
  Badge,
  Paper,
  Stack,
  Text,
  SegmentedControl,
  Box,
  ScrollArea,
  ThemeIcon,
  UnstyledButton,
} from '@mantine/core'
import { Calendar } from '@mantine/dates'
import { useProgramStore } from '@/store/programStore'
import { phaseColor } from '@/utils/phases'
import SessionDrawer from '@/components/sessions/SessionDrawer'
import { startOfWeek, format } from 'date-fns'
import { Check } from 'lucide-react'
import dayjs from 'dayjs'

type ViewType = 'Month' | 'Agenda'

export default function CalendarPage() {
  const { program, isLoading } = useProgramStore()
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [view, setView] = useState<ViewType>('Agenda')
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.matchMedia('(max-width: 639px)').matches : false
  )
  const [monthDate, setMonthDate] = useState<Date>(new Date())

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 639px)')
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [])

  useEffect(() => {
    if (isMobile && view === 'Month') setView('Agenda')
  }, [isMobile, view])

  // Build a map of date string -> session for fast lookup
  const sessionsByDate = useMemo(() => {
    const map = new Map<string, typeof program extends null ? never : NonNullable<typeof program>['sessions'][number]>()
    if (!program) return map
    for (const session of program.sessions) {
      map.set(session.date, session)
    }
    return map
  }, [program])

  // Group sessions by week for agenda view
  const weeklyGroups = useMemo(() => {
    if (!program) return []
    const groups = new Map<string, typeof program['sessions']>()

    const sorted = [...program.sessions].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    )

    for (const session of sorted) {
      const weekStart = format(startOfWeek(new Date(session.date), { weekStartsOn: 0 }), 'yyyy-MM-dd')
      const existing = groups.get(weekStart)
      if (existing) {
        existing.push(session)
      } else {
        groups.set(weekStart, [session])
      }
    }

    return Array.from(groups.entries()).map(([weekStart, sessions]) => ({
      weekStart,
      weekLabel: format(new Date(weekStart), 'MMM d'),
      sessions,
    }))
  }, [program])

  const selectedSession = selectedDate ? sessionsByDate.get(selectedDate) ?? null : null
  const selectedSessionIndex = selectedDate
    ? program?.sessions.findIndex((s) => s.date === selectedDate) ?? -1
    : -1

  // Map date -> phase color for the month view dots
  const dateColorMap = useMemo(() => {
    const map = new Map<string, string>()
    if (!program) return map
    for (const session of program.sessions) {
      const phase = program.phases.find((p) => p.name === session.phase?.name)
      const color = phase ? phaseColor(phase, program.phases) : '#94a3b8'
      map.set(session.date, color)
    }
    return map
  }, [program])

  if (isLoading || !program) {
    return (
      <Stack align="center" justify="center" style={{ minHeight: '50vh' }}>
        <Text c="dimmed" size="lg">Loading...</Text>
      </Stack>
    )
  }

  const handleDayClick = (dateStr: string) => {
    const session = sessionsByDate.get(dateStr)
    if (session) {
      setSelectedDate(dateStr)
    }
  }

  // renderDay receives a DateStringValue (YYYY-MM-DD string), not a Date
  // The Day component already wraps children in UnstyledButton, so we only return visual content
  const renderDay = (date: string) => {
    const color = dateColorMap.get(date)
    const session = sessionsByDate.get(date)

    return (
      <Stack gap={0} align="center" justify="center" style={{ minHeight: 40 }}>
        <Text size="sm">{dayjs(date).date()}</Text>
        {color && (
          <Box
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: session?.completed ? color : `${color}80`,
              opacity: session?.completed ? 1 : 0.7,
            }}
          />
        )}
      </Stack>
    )
  }

  // getDayProps handles click events on day cells
  const getDayProps = (date: string) => {
    const session = sessionsByDate.get(date)
    return {
      onClick: () => handleDayClick(date),
      disabled: !session,
    }
  }

  return (
    <Stack gap="sm" style={{ height: 'calc(100dvh - 200px)' }}>
      {/* Header */}
      <Group justify="space-between" wrap="nowrap">
        <Text size="xl" fw={700}>Calendar</Text>

        <Group gap="xs" wrap="nowrap">
          {/* Phase Legend */}
          <Group gap={4} style={{ overflowX: 'auto' }} wrap="nowrap">
            {program.phases.map((phase, idx) => (
              <Badge
                key={idx}
                variant="dot"
                color={phaseColor(phase, program.phases)}
                size={isMobile ? 'xs' : 'sm'}
                styles={{
                  root: { backgroundColor: 'transparent' },
                  label: { fontSize: isMobile ? 10 : undefined },
                }}
              >
                {phase.name}
              </Badge>
            ))}
          </Group>

          {!isMobile && (
            <SegmentedControl
              size="xs"
              data={['Month', 'Agenda']}
              value={view}
              onChange={(val) => setView(val as ViewType)}
            />
          )}
        </Group>
      </Group>

      {/* Calendar Content */}
      <Paper withBorder p={isMobile ? 'xs' : 'md'} style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <ScrollArea h="100%">
          {view === 'Month' ? (
            <Calendar
              value={monthDate}
              onChange={(date) => {
                if (date) setMonthDate(date)
              }}
              renderDay={renderDay}
              getDayProps={getDayProps}
              size={isMobile ? 'sm' : 'md'}
            />
          ) : (
            <Stack gap="md">
              {weeklyGroups.map(({ weekStart, weekLabel, sessions }) => (
                <Stack key={weekStart} gap={4}>
                  <Text size="sm" fw={600} c="dimmed">
                    Week of {weekLabel}
                  </Text>
                  {sessions.map((session) => {
                    const phase = program.phases.find((p) => p.name === session.phase?.name)
                    const color = phase ? phaseColor(phase, program.phases) : '#94a3b8'
                    const exerciseNames = session.exercises.length > 0
                      ? session.exercises.map((e) => e.name).join(', ')
                      : 'Rest Day'

                    return (
                      <UnstyledButton
                        key={session.date}
                        onClick={() => setSelectedDate(session.date)}
                      >
                        <Paper
                          withBorder
                          p="xs"
                          style={{
                            borderLeft: `4px solid ${color}`,
                            opacity: session.completed ? 1 : 0.7,
                          }}
                        >
                          <Group justify="space-between" wrap="nowrap">
                            <Group gap="xs" wrap="nowrap">
                              <Text size="sm" fw={500} style={{ minWidth: 60 }}>
                                {format(new Date(session.date), 'MMM d')}
                              </Text>
                              <Badge
                                size="xs"
                                variant="filled"
                                color={color}
                              >
                                {session.phase?.name || 'Unknown'}
                              </Badge>
                              <Text
                                size="sm"
                                c="dimmed"
                                lineClamp={1}
                                style={{ maxWidth: isMobile ? 120 : 300 }}
                              >
                                {exerciseNames}
                              </Text>
                            </Group>
                            {session.completed && (
                              <ThemeIcon size="sm" variant="subtle" color="green" radius="xl">
                                <Check size={14} />
                              </ThemeIcon>
                            )}
                          </Group>
                        </Paper>
                      </UnstyledButton>
                    )
                  })}
                </Stack>
              ))}
            </Stack>
          )}
        </ScrollArea>
      </Paper>

      {/* Session Drawer */}
      <SessionDrawer
        isOpen={selectedDate !== null}
        onClose={() => setSelectedDate(null)}
        session={selectedSession ?? null}
        sessionIndex={selectedSessionIndex}
        sessionArrayIndex={selectedSessionIndex}
      />
    </Stack>
  )
}
