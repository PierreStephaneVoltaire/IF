import { useMemo, useState } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { displayWeight, toDisplayUnit, roundToNearest } from '@/utils/units'
import { clsx } from 'clsx'
import { Edit3, Check } from 'lucide-react'

interface PercentRow {
  pct: number
  squat: number
  bench: number
  deadlift: number
  total: number
}

function buildPercentTable(squat: number, bench: number, deadlift: number): PercentRow[] {
  return Array.from({ length: 21 }, (_, i) => {
    const pct = 50 + i * 2.5
    return {
      pct,
      squat: roundToNearest(squat * pct / 100, 2.5),
      bench: roundToNearest(bench * pct / 100, 2.5),
      deadlift: roundToNearest(deadlift * pct / 100, 2.5),
      total: roundToNearest((squat + bench + deadlift) * pct / 100, 2.5),
    }
  })
}

export default function PercentTable() {
  const { program } = useProgramStore()
  const { unit } = useSettingsStore()
  const [isEditing, setIsEditing] = useState(false)
  const [editValues, setEditValues] = useState({
    squat: 0,
    bench: 0,
    deadlift: 0,
  })

  // Get current maxes from program
  const maxes = useMemo(() => {
    if (!program?.meta) return { squat: 0, bench: 0, deadlift: 0 }
    return {
      squat: program.meta.target_squat_kg || 0,
      bench: program.meta.target_bench_kg || 0,
      deadlift: program.meta.target_dl_kg || 0,
    }
  }, [program])

  // Initialize edit values when maxes change
  useMemo(() => {
    setEditValues(maxes)
  }, [maxes])

  // Build the table
  const table = useMemo(() => {
    return buildPercentTable(editValues.squat, editValues.bench, editValues.deadlift)
  }, [editValues])

  // Highlight percentages
  const highlightPcts = [65, 70, 75, 80, 85, 90, 95, 100]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold mb-2">% of Max Table</h2>
        <p className="text-muted-foreground">
          Calculate weights at different percentages of your maxes
        </p>
      </div>

      {/* Max Inputs */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-medium">Current Maxes ({unit})</h3>
          <button
            onClick={() => setIsEditing(!isEditing)}
            className={clsx(
              'px-3 py-1 rounded-md text-sm font-medium transition-colors',
              isEditing
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-accent'
            )}
          >
            {isEditing ? <Check className="w-4 h-4" /> : <Edit3 className="w-4 h-4" />}
            {isEditing ? ' Done' : ' Edit'}
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Squat</label>
            {isEditing ? (
              <input
                type="number"
                value={toDisplayUnit(editValues.squat, unit) || ''}
                onChange={(e) => setEditValues((v) => ({
                  ...v,
                  squat: Number(e.target.value) / (unit === 'lb' ? 2.20462 : 1) || 0
                }))}
                className="w-full px-2 py-1 border border-border rounded bg-background text-lg font-bold"
                step={unit === 'kg' ? 2.5 : 5}
              />
            ) : (
              <p className="text-lg font-bold">{displayWeight(maxes.squat, unit)}</p>
            )}
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Bench</label>
            {isEditing ? (
              <input
                type="number"
                value={toDisplayUnit(editValues.bench, unit) || ''}
                onChange={(e) => setEditValues((v) => ({
                  ...v,
                  bench: Number(e.target.value) / (unit === 'lb' ? 2.20462 : 1) || 0
                }))}
                className="w-full px-2 py-1 border border-border rounded bg-background text-lg font-bold"
                step={unit === 'kg' ? 2.5 : 5}
              />
            ) : (
              <p className="text-lg font-bold">{displayWeight(maxes.bench, unit)}</p>
            )}
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Deadlift</label>
            {isEditing ? (
              <input
                type="number"
                value={toDisplayUnit(editValues.deadlift, unit) || ''}
                onChange={(e) => setEditValues((v) => ({
                  ...v,
                  deadlift: Number(e.target.value) / (unit === 'lb' ? 2.20462 : 1) || 0
                }))}
                className="w-full px-2 py-1 border border-border rounded bg-background text-lg font-bold"
                step={unit === 'kg' ? 2.5 : 5}
              />
            ) : (
              <p className="text-lg font-bold">{displayWeight(maxes.deadlift, unit)}</p>
            )}
          </div>
        </div>

        {isEditing && (
          <p className="text-xs text-muted-foreground mt-2">
            Editing changes the table below. Save to program to persist.
          </p>
        )}
      </div>

      {/* Percent Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-secondary">
                <th className="px-3 py-2 text-left font-medium">%</th>
                <th className="px-3 py-2 text-right font-medium">Squat</th>
                <th className="px-3 py-2 text-right font-medium">Bench</th>
                <th className="px-3 py-2 text-right font-medium">Deadlift</th>
                <th className="px-3 py-2 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {table.map((row) => (
                <tr
                  key={row.pct}
                  className={clsx(
                    'border-t border-border',
                    highlightPcts.includes(row.pct) && 'bg-primary/5',
                    row.pct === 100 && 'font-bold bg-primary/10'
                  )}
                >
                  <td className={clsx(
                    'px-3 py-1.5',
                    highlightPcts.includes(row.pct) && 'font-medium text-primary'
                  )}>
                    {row.pct}%
                  </td>
                  <td className="px-3 py-1.5 text-right">{displayWeight(row.squat, unit)}</td>
                  <td className="px-3 py-1.5 text-right">{displayWeight(row.bench, unit)}</td>
                  <td className="px-3 py-1.5 text-right">{displayWeight(row.deadlift, unit)}</td>
                  <td className="px-3 py-1.5 text-right font-medium">{displayWeight(row.total, unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Reference */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Warmup', pct: 50 },
          { label: 'Working', pct: 70 },
          { label: 'Heavy', pct: 85 },
          { label: 'Max', pct: 100 },
        ].map(({ label, pct }) => {
          const row = table.find((r) => r.pct === pct)
          if (!row) return null
          return (
            <div key={pct} className="bg-secondary rounded-lg p-3 text-center">
              <p className="text-xs text-muted-foreground mb-1">{label} ({pct}%)</p>
              <p className="font-bold">{displayWeight(row.total, unit)}</p>
              <p className="text-xs text-muted-foreground">total</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
