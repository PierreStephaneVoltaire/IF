import { useState, useEffect, useMemo } from 'react'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import type { GlossaryExercise } from '@powerlifting/types'
import { fetchGlossary } from '@/api/client'
import { useProgramStore } from '@/store/programStore'
import { weeklySetsByMuscleGroup, weeklyVolumeByMuscleGroup } from '@/utils/volume'
import { MUSCLE_DISPLAY_NAMES } from '@/utils/muscles'
import StrengthProgressChart from '@/components/charts/StrengthProgressChart'
import VolumeChart from '@/components/charts/VolumeChart'
import WeightChart from '@/components/charts/WeightChart'
import IntensityChart from '@/components/charts/IntensityChart'
import RpeChart from '@/components/charts/RpeChart'

const MUSCLE_COLORS: Record<string, string> = {
  quads: '#ef4444',
  hamstrings: '#f97316',
  glutes: '#eab308',
  calves: '#84cc16',
  hip_flexors: '#22c55e',
  chest: '#3b82f6',
  triceps: '#6366f1',
  front_delts: '#8b5cf6',
  side_delts: '#a855f7',
  rear_delts: '#d946ef',
  lats: '#ec4899',
  traps: '#14b8a6',
  rhomboids: '#06b6d4',
  teres_major: '#0ea5e9',
  biceps: '#f43f5e',
  forearms: '#78716c',
  erectors: '#64748b',
  lower_back: '#78716c',
  core: '#a3a3a3',
  obliques: '#d4d4d4',
}

export default function ChartsPage() {
  const { program } = useProgramStore()
  const [glossary, setGlossary] = useState<GlossaryExercise[]>([])
  const [block, setBlock] = useState('current')

  useEffect(() => {
    fetchGlossary().then(setGlossary).catch(() => {})
  }, [])

  const availableBlocks = useMemo(() => {
    if (!program) return ['current']
    const blocks = new Set<string>()
    for (const s of program.sessions) blocks.add(s.block ?? 'current')
    return Array.from(blocks).sort()
  }, [program])

  const weeklyMuscleData = useMemo(() => {
    if (!program || glossary.length === 0) return []
    return weeklySetsByMuscleGroup(program.sessions, glossary, block)
  }, [program, glossary, block])

  const weeklyMuscleVolumeData = useMemo(() => {
    if (!program || glossary.length === 0) return []
    return weeklyVolumeByMuscleGroup(program.sessions, glossary, block)
  }, [program, glossary, block])

  // Get the muscle group keys present in the data (exclude 'week')
  const muscleKeys = useMemo(() => {
    const keys = new Set<string>()
    for (const row of weeklyMuscleData) {
      for (const key of Object.keys(row)) {
        if (key !== 'week' && row[key] > 0) {
          keys.add(key)
        }
      }
    }
    return Array.from(keys).sort()
  }, [weeklyMuscleData])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Charts</h1>
          <p className="text-muted-foreground text-sm">
            Visualize your training progress over time
          </p>
        </div>
        {availableBlocks.length > 1 && (
          <select
            value={block}
            onChange={(e) => setBlock(e.target.value)}
            className="px-3 py-1.5 border border-border rounded-md bg-background text-sm"
          >
            {availableBlocks.map((b) => (
              <option key={b} value={b}>
                {b === 'current' ? 'Current Block' : b}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Mobile: Stack all charts vertically with min height */}
      {/* Desktop: 2x2 grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="min-h-[300px]">
          <StrengthProgressChart block={block} />
        </div>
        <div className="min-h-[300px]">
          <VolumeChart block={block} />
        </div>
        <div className="min-h-[300px]">
          <WeightChart />
        </div>
        <div className="min-h-[300px]">
          <IntensityChart block={block} />
        </div>
      </div>

      <div className="min-h-[250px]">
        <RpeChart block={block} />
      </div>

      {/* Muscle group charts */}
      {weeklyMuscleData.length > 0 && muscleKeys.length > 0 && (
        <>
          {/* Weekly Sets - stacked bar */}
          <div className="bg-card border border-border rounded-lg p-4 min-h-[350px]">
            <h3 className="font-medium mb-2">Weekly Sets per Muscle Group</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={weeklyMuscleData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" tickFormatter={(v: number) => `W${v}`} />
                <YAxis tickFormatter={(v: number) => `${v}`} />
                <Tooltip formatter={(value: number) => [`${value.toFixed(1)} sets`]} />
                <Legend />
                {muscleKeys.map((key) => (
                  <Bar
                    key={key}
                    dataKey={key}
                    stackId="mg"
                    fill={MUSCLE_COLORS[key] ?? '#94a3b8'}
                    name={MUSCLE_DISPLAY_NAMES[key as keyof typeof MUSCLE_DISPLAY_NAMES] ?? key}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Weekly Volume per Muscle Group - individual line charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {muscleKeys.map((key) => (
              <div key={key} className="bg-card border border-border rounded-lg p-4 min-h-[250px]">
                <h3 className="font-medium mb-2">
                  {MUSCLE_DISPLAY_NAMES[key as keyof typeof MUSCLE_DISPLAY_NAMES] ?? key} — Weekly Volume
                </h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={weeklyMuscleVolumeData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" tickFormatter={(v: number) => `W${v}`} />
                    <YAxis tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`} />
                    <Tooltip formatter={(value: number) => [`${value.toFixed(0)} kg`]} />
                    <Line
                      type="monotone"
                      dataKey={key}
                      stroke={MUSCLE_COLORS[key] ?? '#94a3b8'}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
