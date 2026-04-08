import { useState, useMemo } from 'react'
import { PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { allTimeMaxByExercise, maxByCategoryInWindow, categorizeExercise } from '@/utils/volume'
import { displayWeight } from '@/utils/units'
import type { LiftCategory } from '@/utils/volume'
import type { Session } from '@powerlifting/types'

const BIG3_COLORS: Record<string, string> = {
  squat: '#ef4444',
  bench: '#3b82f6',
  deadlift: '#22c55e',
}

const BIG3_LABELS: Record<string, string> = {
  squat: 'Squat',
  bench: 'Bench',
  deadlift: 'Deadlift',
}

function big3PieData(maxes: Record<string, number>) {
  return (['squat', 'bench', 'deadlift'] as LiftCategory[])
    .filter((cat) => maxes[cat] > 0)
    .map((cat) => ({
      name: BIG3_LABELS[cat],
      value: maxes[cat],
      category: cat,
    }))
}

function Big3Pie({ maxes }: { maxes: Record<string, number> }) {
  const data = big3PieData(maxes)
  if (data.length === 0) return <p className="text-muted-foreground text-sm">No data.</p>

  return (
    <ResponsiveContainer width="100%" height={250}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={90}
          label={({ name, value }: { name: string; value: number }) => `${name}: ${value}kg`}
        >
          {data.map((entry) => (
            <Cell key={entry.category} fill={BIG3_COLORS[entry.category]} />
          ))}
        </Pie>
        <Tooltip formatter={(value: number) => [`${value} kg`]} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  )
}

export default function MaxesPage() {
  const { program } = useProgramStore()
  const { unit } = useSettingsStore()
  const [block, setBlock] = useState('current')

  const availableBlocks = useMemo(() => {
    if (!program) return ['current']
    const blocks = new Set<string>()
    for (const s of program.sessions) blocks.add(s.block ?? 'current')
    return Array.from(blocks).sort()
  }, [program])

  const allTimeMaxes = useMemo(() => {
    if (!program) return new Map<string, { kg: number; displayName: string }>()
    return allTimeMaxByExercise(program.sessions, block)
  }, [program, block])

  const allTimeBig3 = useMemo(() => {
    const result: Record<string, number> = { squat: 0, bench: 0, deadlift: 0 }
    allTimeMaxes.forEach(({ kg }, key) => {
      const cat = categorizeExercise(key)
      if (cat in result && kg > result[cat]) result[cat] = kg
    })
    return result
  }, [allTimeMaxes])

  const maxTableRows = useMemo(() => {
    return Array.from(allTimeMaxes.entries())
      .sort((a, b) => b[1].kg - a[1].kg)
  }, [allTimeMaxes])

  const upcomingComps = useMemo(() => {
    if (!program?.competitions) return []
    return program.competitions
      .filter((c) => c.status !== 'skipped' && new Date(c.date) >= new Date())
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [program])

  const compWindows = useMemo(() => {
    if (!program || upcomingComps.length === 0) return []

    const allCompDates = [...upcomingComps.map((c) => c.date)].sort()
    const programStart = program.meta?.program_start ?? program.sessions[0]?.date ?? ''

    return upcomingComps.map((comp) => {
      const compIdx = allCompDates.indexOf(comp.date)
      const windowStart = compIdx > 0 ? allCompDates[compIdx - 1] : programStart
      const maxes = maxByCategoryInWindow(program.sessions, windowStart, comp.date, ['squat', 'bench', 'deadlift'], block)
      const targets = comp.targets
        ? { squat: comp.targets.squat_kg, bench: comp.targets.bench_kg, deadlift: comp.targets.deadlift_kg }
        : null
      return { comp, maxes, targets }
    })
  }, [program, upcomingComps, block])

  if (!program) {
    return <p className="text-muted-foreground">Loading...</p>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Maxes</h1>
          <p className="text-muted-foreground text-sm">
            Heaviest weight per exercise and big 3 strength distribution
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

      {/* All-Time Max Table */}
      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="font-medium mb-2">All-Time Maxes</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-1 px-2 font-medium text-muted-foreground">Exercise</th>
                <th className="text-right py-1 px-2 font-medium text-muted-foreground">Max</th>
              </tr>
            </thead>
            <tbody>
              {maxTableRows.map(([, { kg, displayName }]) => (
                <tr key={displayName} className="border-b border-border/50">
                  <td className="py-1 px-2">{displayName}</td>
                  <td className="text-right py-1 px-2 font-mono">{displayWeight(kg, unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Big 3 Pie — All Time */}
      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="font-medium mb-2">Big 3 Distribution (All Time)</h3>
        <Big3Pie maxes={allTimeBig3} />
      </div>

      {/* Per-Competition Goal Pies */}
      {compWindows.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-medium">Competition Goals</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {compWindows.map(({ comp, maxes, targets }) => (
              <div key={comp.date} className="bg-card border border-border rounded-lg p-4">
                <div className="mb-2">
                  <p className="font-medium">{comp.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {comp.date} &middot; {comp.federation} &middot; {comp.weight_class_kg}kg
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Current Max</p>
                    <Big3Pie maxes={maxes} />
                  </div>
                  {targets && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Target</p>
                      <Big3Pie maxes={targets} />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
