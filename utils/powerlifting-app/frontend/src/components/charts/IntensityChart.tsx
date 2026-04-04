import { useMemo } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'

export default function IntensityChart() {
  const { program } = useProgramStore()
  const { unit } = useSettingsStore()

  const data = useMemo(() => {
    if (!program?.meta) return []

    const targets = {
      squat: program.meta.target_squat_kg || 0,
      bench: program.meta.target_bench_kg || 0,
      deadlift: program.meta.target_dl_kg || 0,
    }

    return program.sessions
      .filter((s) => s.completed)
      .map((session) => {
        let squatPct = 0
        let benchPct = 0
        let dlPct = 0

        for (const ex of session.exercises) {
          if (!ex.kg) continue
          const name = ex.name.toLowerCase()

          if (name.includes('squat') && targets.squat > 0) {
            squatPct = Math.max(squatPct, (ex.kg / targets.squat) * 100)
          } else if (name.includes('bench') && targets.bench > 0) {
            benchPct = Math.max(benchPct, (ex.kg / targets.bench) * 100)
          } else if ((name.includes('deadlift') || name.includes('dl')) && targets.deadlift > 0) {
            dlPct = Math.max(dlPct, (ex.kg / targets.deadlift) * 100)
          }
        }

        return {
          date: session.date,
          squat: squatPct,
          bench: benchPct,
          deadlift: dlPct,
        }
      })
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [program])

  if (!program || data.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-4 flex items-center justify-center min-h-0 flex-1">
        <p className="text-muted-foreground text-sm">No completed sessions with weights logged.</p>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="font-medium mb-2">Intensity (% of Target Max)</h3>
      <div>
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" />
            <YAxis domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)}%`]}
              labelFormatter={(label: string) => `Date: ${label}`}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="squat"
              stroke="#ef4444"
              fill="#ef444433"
              name="Squat"
            />
            <Area
              type="monotone"
              dataKey="bench"
              stroke="#3b82f6"
              fill="#3b82f633"
              name="Bench"
            />
            <Area
              type="monotone"
              dataKey="deadlift"
              stroke="#22c55e"
              fill="#22c55e33"
              name="Deadlift"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
