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
import { weeklyVolumeByCategory6 } from '@/utils/volume'
import { displayWeight } from '@/utils/units'

const CATEGORY_COLORS: Record<string, string> = {
  squat: '#ef4444',
  bench: '#3b82f6',
  deadlift: '#22c55e',
  upper_accessory: '#f97316',
  lower_accessory: '#a855f7',
  core_accessory: '#06b6d4',
}

const CATEGORY_LABELS: Record<string, string> = {
  squat: 'Squat',
  bench: 'Bench',
  deadlift: 'Deadlift',
  upper_accessory: 'Upper Accessory',
  lower_accessory: 'Lower Accessory',
  core_accessory: 'Core Accessory',
}

const CATEGORIES = ['squat', 'bench', 'deadlift', 'upper_accessory', 'lower_accessory', 'core_accessory'] as const

export default function VolumeChart() {
  const { program } = useProgramStore()
  const { unit } = useSettingsStore()

  const data = useMemo(() => {
    if (!program) return []
    return weeklyVolumeByCategory6(program.sessions)
  }, [program])

  if (!program || data.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-4 flex items-center justify-center min-h-0 flex-1">
        <p className="text-muted-foreground text-sm">No session data available</p>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="font-medium mb-2">Weekly Volume by Category</h3>
      <div>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="week" tickFormatter={(v) => `W${v}`} />
            <YAxis
              tickFormatter={(value: number) => `${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(value: number) => [`${(value / 1000).toFixed(1)}k volume`]}
            />
            <Legend />
            {CATEGORIES.map((cat) => (
              <Bar
                key={cat}
                dataKey={cat}
                stackId="a"
                fill={CATEGORY_COLORS[cat]}
                name={CATEGORY_LABELS[cat]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
