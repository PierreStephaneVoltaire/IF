import { useMemo } from 'react'
import { useProgramStore } from '@/store/programStore'
import { parseISO, differenceInDays, format } from 'date-fns'
import { phaseColor } from '@/utils/phases'

export default function TimelinePage() {
  const { program, isLoading } = useProgramStore()

  const timelineData = useMemo(() => {
    if (!program) return null

    const startDate = parseISO(program.meta.program_start)
    const compDate = parseISO(program.meta.comp_date)
    const totalDays = differenceInDays(compDate, startDate)
    const today = new Date()
    const todayOffset = differenceInDays(today, startDate)

    return {
      startDate,
      compDate,
      totalDays,
      todayOffset,
      phases: program.phases.map((phase) => ({
        ...phase,
        startOffset: (phase.start_week - 1) * 7,
        endOffset: phase.end_week * 7,
      })),
      sessions: program.sessions.map((s) => ({
        ...s,
        offset: differenceInDays(parseISO(s.date), startDate),
      })),
      competitions: program.competitions.filter((c) => c.status !== 'skipped'),
    }
  }, [program])

  if (isLoading || !program || !timelineData) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    )
  }

  const width = Math.max(800, timelineData.totalDays * 3)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Program Timeline</h1>

      {/* Phase Legend */}
      <div className="flex flex-wrap gap-4">
        {program.phases.map((phase, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: phaseColor(phase, program.phases) }}
            />
            <span className="text-sm">
              {phase.name} (W{phase.start_week}-W{phase.end_week})
            </span>
          </div>
        ))}
      </div>

      {/* Timeline SVG */}
      <div className="overflow-x-auto border border-border rounded-lg">
        <svg width={width} height={300} className="bg-card">
          {/* Phase bands */}
          {timelineData.phases.map((phase, idx) => {
            const x1 = (phase.startOffset / timelineData.totalDays) * width
            const x2 = (phase.endOffset / timelineData.totalDays) * width
            const color = phaseColor(phase, program.phases)

            return (
              <rect
                key={idx}
                x={x1}
                y={0}
                width={x2 - x1}
                height={40}
                fill={color}
                opacity={0.3}
              />
            )
          })}

          {/* Session dots */}
          {timelineData.sessions.map((session, idx) => {
            const x = (session.offset / timelineData.totalDays) * width
            const color = phaseColor(session.phase, program.phases)

            return (
              <g key={idx}>
                <circle
                  cx={x}
                  cy={60}
                  r={session.completed ? 6 : 4}
                  fill={color}
                  opacity={session.completed ? 1 : 0.5}
                />
                <title>
                  {format(parseISO(session.date), 'MMM d')}: {session.exercises.length} exercises
                </title>
              </g>
            )
          })}

          {/* Competition markers */}
          {timelineData.competitions.map((comp, idx) => {
            const compDate = parseISO(comp.date)
            const offset = differenceInDays(compDate, timelineData.startDate)
            const x = (offset / timelineData.totalDays) * width

            return (
              <g key={idx}>
                <line
                  x1={x}
                  y1={0}
                  x2={x}
                  y2={280}
                  stroke="#ef4444"
                  strokeWidth={2}
                  strokeDasharray="4,4"
                />
                <text x={x + 4} y={20} fontSize={12} fill="#ef4444">
                  {comp.name}
                </text>
              </g>
            )
          })}

          {/* Today line */}
          {timelineData.todayOffset >= 0 && timelineData.todayOffset <= timelineData.totalDays && (
            <line
              x1={(timelineData.todayOffset / timelineData.totalDays) * width}
              y1={0}
              x2={(timelineData.todayOffset / timelineData.totalDays) * width}
              y2={280}
              stroke="#22c55e"
              strokeWidth={2}
            />
          )}

          {/* Week labels */}
          {Array.from({ length: Math.ceil(timelineData.totalDays / 7) }, (_, i) => i + 1).map((week) => {
            const x = ((week - 1) * 7 / timelineData.totalDays) * width
            return (
              <text
                key={week}
                x={x}
                y={295}
                fontSize={10}
                fill="#94a3b8"
              >
                W{week}
              </text>
            )
          })}
        </svg>
      </div>

      {/* Info */}
      <div className="text-sm text-muted-foreground">
        <p>Program: {format(timelineData.startDate, 'MMM d, yyyy')} → {format(timelineData.compDate, 'MMM d, yyyy')}</p>
        <p>Total: {timelineData.totalDays} days ({Math.ceil(timelineData.totalDays / 7)} weeks)</p>
      </div>
    </div>
  )
}
