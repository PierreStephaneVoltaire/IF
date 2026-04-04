import { useState, useMemo, useEffect } from 'react'
import { useSettingsStore } from '@/store/settingsStore'
import { useProgramStore } from '@/store/programStore'
import {
  calculateDots,
  calculateDotsFromLifts,
  totalForTargetDots,
  dotsAcrossWeightClasses,
  getDotsLevel,
} from '@/utils/dots'
import { displayWeight, kgToLb, toDisplayUnit } from '@/utils/units'
import { clsx } from 'clsx'
import type { Sex } from '@powerlifting/types'

export default function DotsCalculator() {
  const { sex, unit } = useSettingsStore()
  const { program } = useProgramStore()

  const [squatKg, setSquatKg] = useState<number>(0)
  const [benchKg, setBenchKg] = useState<number>(0)
  const [deadliftKg, setDeadliftKg] = useState<number>(0)
  const [bodyweightKg, setBodyweightKg] = useState<number>(0)
  const [targetDots, setTargetDots] = useState<number>(300)

  // Initialize from program maxes
  useMemo(() => {
    if (program?.meta) {
      setSquatKg(program.meta.target_squat_kg || 0)
      setBenchKg(program.meta.target_bench_kg || 0)
      setDeadliftKg(program.meta.target_dl_kg || 0)
      setBodyweightKg(program.meta.current_body_weight_kg || 0)
    }
  }, [program])

  // Calculate DOTS
  const result = useMemo(() => {
    if (!squatKg && !benchKg && !deadliftKg) return null
    return calculateDotsFromLifts(squatKg, benchKg, deadliftKg, bodyweightKg, sex)
  }, [squatKg, benchKg, deadliftKg, bodyweightKg, sex])

  // Get performance level
  const level = useMemo(() => {
    if (!result) return null
    return getDotsLevel(result.dots, sex)
  }, [result, sex])

  // Reverse calculation - total needed for target DOTS
  const totalNeeded = useMemo(() => {
    if (bodyweightKg <= 0) return null
    return totalForTargetDots(targetDots, bodyweightKg, sex)
  }, [targetDots, bodyweightKg, sex])

  // Weight class scenarios
  const weightClassScenarios = useMemo(() => {
    if (!result) return null
    const classes = [59, 66, 74, 83, 93, 105, 120, 130]
    return dotsAcrossWeightClasses(result.total_kg, classes, sex)
  }, [result, sex])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold mb-4">DOTS Calculator</h2>
        <p className="text-muted-foreground">
          Calculate your DOTS score based on your lifts and bodyweight
        </p>
      </div>

      {/* Sex Toggle */}
      <div className="flex gap-2">
        {(['male', 'female'] as Sex[]).map((s) => (
          <button
            key={s}
            onClick={() => useSettingsStore.getState().setSex(s)}
            className={clsx(
              'flex-1 px-4 py-2 rounded-md font-medium transition-colors',
              sex === s
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-accent'
            )}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Input Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Body Weight ({unit})</label>
          <input
            type="number"
            value={toDisplayUnit(bodyweightKg, unit) || ''}
            onChange={(e) => setBodyweightKg(Number(e.target.value) / (unit === 'lb' ? 2.20462 : 1) || 0)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Squat ({unit})</label>
          <input
            type="number"
            value={toDisplayUnit(squatKg, unit) || ''}
            onChange={(e) => setSquatKg(Number(e.target.value) / (unit === 'lb' ? 2.20462 : 1) || 0)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Bench ({unit})</label>
          <input
            type="number"
            value={toDisplayUnit(benchKg, unit) || ''}
            onChange={(e) => setBenchKg(Number(e.target.value) / (unit === 'lb' ? 2.20462 : 1) || 0)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Deadlift ({unit})</label>
          <input
            type="number"
            value={toDisplayUnit(deadliftKg, unit) || ''}
            onChange={(e) => setDeadliftKg(Number(e.target.value) / (unit === 'lb' ? 2.20462 : 1) || 0)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background"
          />
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-6">
          {/* Main Score */}
          <div className="text-center">
            <p className="text-sm text-muted-foreground">DOTS Score</p>
            <p className="text-5xl font-bold text-primary">{result.dots}</p>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-sm text-muted-foreground">Total</p>
              <p className="text-xl font-bold">{displayWeight(result.total_kg, unit)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Body Weight</p>
              <p className="text-xl font-bold">{displayWeight(result.bodyweight_kg, unit)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Level</p>
              <p className={clsx(
                'text-xl font-bold',
                level?.name === 'World-class' ? 'text-primary' :
                level?.name === 'Elite' ? 'text-primary' :
                level?.name === 'Advanced' ? 'text-primary' : ''
              )}>
                {level?.name || 'N/A'}
              </p>
            </div>
          </div>

          {/* Performance Context */}
          {level && (
            <p className="text-center text-sm text-muted-foreground">
              {level.context}
            </p>
          )}
        </div>
      )}

      {/* Reverse Calculator */}
      <div className="bg-card border border-border rounded-lg p-6 space-y-4">
        <h3 className="font-medium">Target DOTS Calculator</h3>
        <p className="text-sm text-muted-foreground">
          What total do you need to hit a target DOTS score?
        </p>

        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="text-sm font-medium">Target DOTS</label>
            <input
              type="number"
              value={targetDots || ''}
              onChange={(e) => setTargetDots(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 border border-border rounded-md bg-background"
              step={5}
            />
          </div>
          {totalNeeded && (
            <div className="flex-1 text-center">
              <p className="text-sm text-muted-foreground">Required Total</p>
              <p className="text-2xl font-bold text-primary">
                {displayWeight(totalNeeded, unit)}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Weight Class Optimizer */}
      {weightClassScenarios && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-4">
          <h3 className="font-medium">DOTS at Different Body Weights</h3>
          <p className="text-sm text-muted-foreground">
            See how your DOTS changes across weight classes
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2">Body Weight</th>
                  <th className="text-right py-2">DOTS</th>
                  <th className="text-right py-2">vs Current</th>
                </tr>
              </thead>
              <tbody>
                {weightClassScenarios.map((scenario) => (
                  <tr
                    key={scenario.bodyweightKg}
                    className={clsx(
                      'border-b border-border',
                      scenario.bodyweightKg === bodyweightKg && 'bg-primary/10'
                    )}
                  >
                    <td className="py-2">{scenario.bodyweightKg} kg</td>
                    <td className="text-right py-2 font-medium">{scenario.dots}</td>
                    <td className={clsx(
                      'text-right py-2',
                      scenario.dots > (result?.dots || 0) ? 'text-primary' :
                      scenario.dots < (result?.dots || 0) ? 'text-destructive' : ''
                    )}>
                      {scenario.dots > (result?.dots || 0) ? '+' : ''}
                      {(scenario.dots - (result?.dots || 0)).toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
