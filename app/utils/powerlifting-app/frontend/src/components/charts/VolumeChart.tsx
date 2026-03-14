import { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { weeklyVolumeByCategory } from '@/utils/volume'
import { displayWeight } from '@/utils/units'

export default function VolumeChart() {
  const { program } = useProgramStore()
  const { unit } = useSettingsStore()

  const data = useMemo(() => {
    if (!program) return []
    return weeklyVolumeByCategory(program.sessions)
  }, [program])

  if (!program || data.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-6 text-center">
        <p className="text-muted-foreground">No session data available</p>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="font-medium mb-4">Weekly Volume by Category</h3>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="week" tickFormatter={(v) => `W${v}`} />
            <YAxis
              tickFormatter={(value: number) => `${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(value: number) => [`${(value / 1000).toFixed(1)}k volume`]}
            />
            <Bar
              dataKey="squat"
              stackId="a"
              fill="#ef4444"
              name="Squat"
            />
            <Bar
              dataKey="bench"
              stackId="a"
              fill="#3b82f6"
              name="Bench"
            />
            <Bar
              dataKey="deadlift"
              stackId="a"
              fill="#22c55e"
              name="Deadlift"
            />
            <Bar
              dataKey="accessory"
              stackId="a"
              fill="#f97316"
              name="Accessory"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
