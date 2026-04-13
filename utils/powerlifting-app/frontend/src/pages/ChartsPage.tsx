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
import { Paper, Title, Text, Select, SimpleGrid, Stack, Group } from '@mantine/core'
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
    <Stack gap="md">
      <Group justify="space-between">
        <div>
          <Title order={2}>Charts</Title>
          <Text size="sm" c="dimmed">
            Visualize your training progress over time
          </Text>
        </div>
        {availableBlocks.length > 1 && (
          <Select
            value={block}
            onChange={(v) => setBlock(v ?? 'current')}
            data={availableBlocks.map((b) => ({
              value: b,
              label: b === 'current' ? 'Current Block' : b,
            }))}
            w={180}
          />
        )}
      </Group>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        <Paper style={{ minHeight: 300 }}>
          <StrengthProgressChart block={block} />
        </Paper>
        <Paper style={{ minHeight: 300 }}>
          <VolumeChart block={block} />
        </Paper>
        <Paper style={{ minHeight: 300 }}>
          <WeightChart />
        </Paper>
        <Paper style={{ minHeight: 300 }}>
          <IntensityChart block={block} />
        </Paper>
      </SimpleGrid>

      <Paper style={{ minHeight: 250 }}>
        <RpeChart block={block} />
      </Paper>

      {/* Muscle group charts */}
      {weeklyMuscleData.length > 0 && muscleKeys.length > 0 && (
        <>
          {/* Weekly Sets - stacked bar */}
          <Paper withBorder p="md" style={{ minHeight: 350 }}>
            <Text fw={500} mb="xs">Weekly Sets per Muscle Group</Text>
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
          </Paper>

          {/* Weekly Volume per Muscle Group - individual line charts */}
          <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
            {muscleKeys.map((key) => (
              <Paper key={key} withBorder p="md" style={{ minHeight: 250 }}>
                <Text fw={500} mb="xs">
                  {MUSCLE_DISPLAY_NAMES[key as keyof typeof MUSCLE_DISPLAY_NAMES] ?? key} — Weekly Volume
                </Text>
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
              </Paper>
            ))}
          </SimpleGrid>
        </>
      )}
    </Stack>
  )
}
