import { useMemo, useState } from 'react'
import { Calendar, dateFnsLocalizer, Views, View } from 'react-big-calendar'
import { format, parse, startOfWeek, getDay, endOfDay, startOfDay } from 'date-fns'
import { enUS } from 'date-fns/locale/en-US'
import { useProgramStore } from '@/store/programStore'
import { phaseColor } from '@/utils/phases'
import SessionDrawer from '@/components/sessions/SessionDrawer'
import 'react-big-calendar/lib/css/react-big-calendar.css'

const locales = {
  'en-US': enUS,
}

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 0 }),
  getDay,
  locales,
})

interface CalendarEvent {
  title: string
  start: Date
  end: Date
  allDay: boolean
  resource: {
    date: string
    completed: boolean
    phaseName: string
    exercises: Array<{ name: string; kg: number | null }>
  }
}

export default function CalendarPage() {
  const { program, isLoading } = useProgramStore()
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [view, setView] = useState<View>(Views.AGENDA)

  const events: CalendarEvent[] = useMemo(() => {
    if (!program) return []

    return program.sessions.map((session) => {
      const sessionDate = new Date(session.date)
      return {
        title: session.exercises.length > 0
          ? session.exercises.map((e) => e.name).join(', ')
          : 'Rest Day',
        start: startOfDay(sessionDate),
        end: endOfDay(sessionDate),
        allDay: true,
        resource: {
          date: session.date,
          completed: session.completed,
          phaseName: session.phase?.name || 'Unknown',
          exercises: session.exercises,
        },
      }
    })
  }, [program])

  const selectedSession = selectedDate
    ? program?.sessions.find((s) => s.date === selectedDate) || null
    : null
  const selectedSessionIndex = selectedDate
    ? program?.sessions.findIndex((s) => s.date === selectedDate) ?? -1
    : -1

  const handleSelectEvent = (event: CalendarEvent) => {
    setSelectedDate(event.resource.date)
  }

  if (isLoading || !program) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    )
  }

  const eventStyleGetter = (event: CalendarEvent) => {
    const phase = program.phases.find((p) => p.name === event.resource.phaseName)
    const bgColor = phase ? phaseColor(phase, program.phases) : '#94a3b8'

    return {
      style: {
        backgroundColor: event.resource.completed ? bgColor : `${bgColor}80`,
        borderRadius: '4px',
        opacity: event.resource.completed ? 1 : 0.7,
        borderLeft: `4px solid ${bgColor}`,
        cursor: 'pointer',
      },
    }
  }

  return (
    <div className="flex flex-col h-[calc(100dvh-220px)] md:h-[calc(100dvh-140px)]">
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h1 className="text-2xl font-bold">Calendar</h1>

        {/* Phase Legend */}
        <div className="flex gap-3 overflow-x-auto">
          {program.phases.map((phase, idx) => (
            <div key={idx} className="flex items-center gap-1 shrink-0">
              <div
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: phaseColor(phase, program.phases) }}
              />
              <span className="text-xs">{phase.name}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-2 sm:p-4 flex-1 min-h-0 overflow-hidden">
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: '100%' }}
          views={[Views.AGENDA, Views.WEEK]}
          view={view}
          onView={setView}
          length={30}
          eventPropGetter={eventStyleGetter}
          tooltipAccessor={(event) =>
            `${event.resource.exercises.map((e) => e.name).join(', ')}${event.resource.completed ? ' ✓' : ''}`
          }
          onSelectEvent={handleSelectEvent}
        />
      </div>

      {/* Session Drawer */}
      <SessionDrawer
        isOpen={selectedDate !== null}
        onClose={() => setSelectedDate(null)}
        session={selectedSession}
        sessionIndex={selectedSessionIndex}
      />
    </div>
  )
}
