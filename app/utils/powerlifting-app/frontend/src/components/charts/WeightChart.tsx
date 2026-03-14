import { useMemo, useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { displayWeight } from '@/utils/units'
import * as api from '@/api/client'
import type { WeightEntry } from '@powerlifting/types'

export default function WeightChart() {
  const { program, version } = useProgramStore()
  const { unit } = useSettingsStore()
  const [entries, setEntries] = useState<WeightEntry[]>([])

  useEffect(() => {
    async function loadEntries() {
      try {
        const log = await api.fetchWeightLog(version)
        setEntries(log || [])
      } catch (err) {
        console.error('Failed to load weight log:', err)
      }
    }
    loadEntries()
  }, [version])

  const data = useMemo(() => {
    if (entries.length === 0) return []

    return [...entries]
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((entry) => ({
        date: entry.date,
        kg: entry.kg,
        lb: entry.kg * 2.20462,
      }))
  }, [entries])

  const weightClassCeiling = program?.meta?.weight_class_kg

  if (entries.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-6 text-center">
        <p className="text-muted-foreground">
          No weight entries logged. Use the Weight Tracker to add entries.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="font-medium mb-4">Body Weight Trend</h3>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" />
            <YAxis
              domain={['auto', 'auto']}
              tickFormatter={(value: number) => `${value.toFixed(1)} kg`}
            />
            <Tooltip
              formatter={(value: number, name: string) => [`${value.toFixed(1)} ${name}`]}
              labelFormatter={(label: string) => `Date: ${label}`}
            />
            <Line
              type="monotone"
              dataKey="kg"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: '#3b82f6' }}
              name="kg"
            />
            {weightClassCeiling && (
              <ReferenceLine
                y={weightClassCeiling}
                stroke="#ef4444"
                strokeDasharray="5 5"
                label={`${weightClassCeiling}kg Class`}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {weightClassCeiling && data && data.length > 0 && (
        <div className="mt-2 text-sm text-muted-foreground">
          Current: {displayWeight(data[data.length - 1].kg, unit)} •
          Target: {weightClassCeiling}kg class
        </div>
      )}
    </div>
  )
}
