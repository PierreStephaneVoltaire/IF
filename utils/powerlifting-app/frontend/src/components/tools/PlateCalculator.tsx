import { useState, useMemo } from 'react'
import { useSettingsStore } from '@/store/settingsStore'
import { useProgramStore } from '@/store/programStore'
import { getPlateLoadout, closestLbLoadout, compAttempts, getPlateColor } from '@/utils/plates'
import { BAR_WEIGHTS_KG, type BarPreset } from '@/constants/plates'
import { displayWeight, kgToLb, toDisplayUnit } from '@/utils/units'
import { clsx } from 'clsx'

type PlateMode = 'kg' | 'lb' | 'both'

export default function PlateCalculator() {
  const { unit, barWeightKg, setBarWeight } = useSettingsStore()
  const { program } = useProgramStore()
  const [targetWeight, setTargetWeight] = useState<number>(0)
  const [barPreset, setBarPreset] = useState<BarPreset>('standard')
  const [plateMode, setPlateMode] = useState<PlateMode>('kg')

  // Get bar weight from preset
  const actualBarWeight = barPreset === 'custom' ? barWeightKg : BAR_WEIGHTS_KG[barPreset]

  // Convert target weight to kg if in lb mode
  const targetKg = useMemo(() => {
    if (unit === 'lb') {
      return targetWeight / 2.20462 // lb to kg
    }
    return targetWeight
  }, [targetWeight, unit])

  // Calculate plate loadout
  const loadout = useMemo(() => {
    if (targetKg <= 0) return null
    return getPlateLoadout(targetKg, actualBarWeight)
  }, [targetKg, actualBarWeight])

  // Calculate LB loadout for comparison
  const lbLoadout = useMemo(() => {
    if (targetKg <= 0 || plateMode === 'lb' || plateMode === 'both') return null
    return closestLbLoadout(targetKg, actualBarWeight)
  }, [targetKg, actualBarWeight, plateMode])

  // Competition attempt suggestions
  const attempts = useMemo(() => {
    if (!program?.meta?.target_total_kg) return null
    return compAttempts(program.meta.target_total_kg)
  }, [program])

  // Quick presets from maxes
  const quickPresets = useMemo(() => {
    if (!program?.meta) return []
    const { target_squat_kg, target_bench_kg, target_dl_kg } = program.meta
    return [
      { label: 'Squat Target', kg: target_squat_kg },
      { label: 'Bench Target', kg: target_bench_kg },
      { label: 'DL Target', kg: target_dl_kg },
    ]
  }, [program])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold mb-4">Plate Calculator</h2>
        <p className="text-muted-foreground">
          Calculate how to load the barbell for your target weight
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Target Weight Input */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Target Weight</label>
          <div className="flex gap-2">
            <input
              type="number"
              value={targetWeight || ''}
              onChange={(e) => setTargetWeight(Number(e.target.value) || 0)}
              className="flex-1 px-3 py-2 border border-border rounded-md bg-background"
              placeholder={unit === 'kg' ? 'kg' : 'lb'}
              step={unit === 'kg' ? 2.5 : 5}
            />
            <span className="px-3 py-2 bg-secondary rounded-md text-sm">
              {unit.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Bar Preset */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Bar Weight</label>
          <select
            value={barPreset}
            onChange={(e) => setBarPreset(e.target.value as BarPreset)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background"
          >
            <option value="standard">Standard (20kg)</option>
            <option value="womens">Women's (15kg)</option>
            <option value="deadlift">Deadlift (25kg)</option>
            <option value="custom">Custom</option>
          </select>
          {barPreset === 'custom' && (
            <input
              type="number"
              value={barWeightKg || ''}
              onChange={(e) => setBarWeight(Number(e.target.value) || 20)}
              className="w-full px-3 py-2 border border-border rounded-md bg-background"
              placeholder="kg"
            />
          )}
        </div>

        {/* Plate Mode */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Plate Mode</label>
          <div className="flex gap-2">
            {(['kg', 'lb', 'both'] as PlateMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setPlateMode(mode)}
                className={clsx(
                  'flex-1 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  plateMode === mode
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-secondary-foreground hover:bg-accent'
                )}
              >
                {mode === 'kg' ? 'KG Plates' : mode === 'lb' ? 'LB Plates' : 'Both'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Presets */}
      {quickPresets && quickPresets.length > 0 && (
        <div className="space-y-2">
          <label className="text-sm font-medium">Quick Presets</label>
          <div className="flex flex-wrap gap-2">
            {quickPresets.map((preset) => (
              <button
                key={preset.label}
                onClick={() => {
                  setTargetWeight(unit === 'kg' ? preset.kg : kgToLb(preset.kg))
                }}
                className="px-3 py-1 bg-secondary rounded-md text-sm hover:bg-accent transition-colors"
              >
                {preset.label} ({displayWeight(preset.kg, unit)})
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {loadout && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-6">
          {/* Summary */}
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm text-muted-foreground">Target</p>
              <p className="text-2xl font-bold">{displayWeight(targetKg, unit)}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">Achievable</p>
              <p className={clsx(
                'text-2xl font-bold',
                loadout.achievable ? 'text-primary' : 'text-destructive'
              )}>
                {displayWeight(loadout.totalKg, unit)}
              </p>
            </div>
          </div>

          {!loadout.achievable && (
            <p className="text-sm text-destructive">
              Cannot achieve exact weight. Remainder: {loadout.remainder.toFixed(2)} kg
            </p>
          )}

          {/* Plate Visualization */}
          <div className="flex items-center justify-center gap-4 py-6">
            {/* Left plates - smallest at edge, largest closest to bar */}
            <div className="flex items-center gap-1">
              {[...loadout.plates].reverse().map((plate, idx) => (
                <div
                  key={idx}
                  className="rounded-sm flex items-center justify-center text-xs font-bold"
                  style={{
                    width: `${Math.min(40 + plate * 2, 80)}px`,
                    height: `${Math.min(20 + plate, 40)}px`,
                    backgroundColor: getPlateColor(plate, plateMode === 'lb' ? 'lb' : 'kg'),
                    color: plate >= 5 ? '#fff' : '#000',
                  }}
                >
                  {plate}
                </div>
              ))}
            </div>

            {/* Bar */}
            <div className="w-4 h-8 bg-gray-400 rounded-sm" />

            {/* Right plates - largest closest to bar, smallest at edge */}
            <div className="flex items-center gap-1">
              {loadout.plates.map((plate, idx) => (
                <div
                  key={idx}
                  className="rounded-sm flex items-center justify-center text-xs font-bold"
                  style={{
                    width: `${Math.min(40 + plate * 2, 80)}px`,
                    height: `${Math.min(20 + plate, 40)}px`,
                    backgroundColor: getPlateColor(plate, plateMode === 'lb' ? 'lb' : 'kg'),
                    color: plate >= 5 ? '#fff' : '#000',
                  }}
                >
                  {plate}
                </div>
              ))}
            </div>
          </div>

          {/* Plate Table */}
          <div className="space-y-2">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2">Plates (per side)</th>
                  <th className="text-right py-2">kg</th>
                  <th className="text-right py-2">lb</th>
                </tr>
              </thead>
              <tbody>
                {Array.from(new Set(loadout.plates)).sort((a, b) => b - a).map((plate) => {
                  const count = loadout.plates.filter((p) => p === plate).length
                  return (
                    <tr key={plate} className="border-b border-border">
                      <td className="py-2">
                        {count}x {plate}kg
                      </td>
                      <td className="text-right py-2">{plate.toFixed(1)} kg</td>
                      <td className="text-right py-2">{kgToLb(plate).toFixed(1)} lb</td>
                    </tr>
                  )
                })}
                <tr className="font-medium">
                  <td className="py-2">Per side total</td>
                  <td className="text-right py-2">{loadout.perSideKg.toFixed(1)} kg</td>
                  <td className="text-right py-2">{kgToLb(loadout.perSideKg).toFixed(1)} lb</td>
                </tr>
                <tr className="font-medium border-t-2 border-border">
                  <td className="py-2">Bar</td>
                  <td className="text-right py-2">{actualBarWeight.toFixed(1)} kg</td>
                  <td className="text-right py-2">{kgToLb(actualBarWeight).toFixed(1)} lb</td>
                </tr>
                <tr className="font-bold bg-primary/10">
                  <td className="py-2">Grand Total</td>
                  <td className="text-right py-2">{loadout.totalKg.toFixed(1)} kg</td>
                  <td className="text-right py-2">{kgToLb(loadout.totalKg).toFixed(1)} lb</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* LB Mode Comparison */}
          {(plateMode === 'lb' || plateMode === 'both') && lbLoadout && (
            <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/20 rounded-md">
              <p className="text-sm">
                <span className="font-medium">With LB plates:</span>{' '}
                {displayWeight(lbLoadout.achievedKg, unit)}
                {Math.abs(lbLoadout.deltaKg) > 0.1 && (
                  <span className="text-amber-600 ml-2">
                    (delta: {lbLoadout.deltaKg > 0 ? '+' : ''}{lbLoadout.deltaKg} kg)
                  </span>
                )}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Competition Attempts */}
      {attempts && (
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="font-medium mb-4">Competition Attempts</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Suggested attempts based on your target total ({displayWeight(program!.meta.target_total_kg, unit)})
          </p>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-secondary rounded-lg">
              <p className="text-sm text-muted-foreground">Opener (85%)</p>
              <p className="text-xl font-bold">{displayWeight(attempts.opener, unit)}</p>
            </div>
            <div className="text-center p-4 bg-secondary rounded-lg">
              <p className="text-sm text-muted-foreground">Second (95%)</p>
              <p className="text-xl font-bold">{displayWeight(attempts.second, unit)}</p>
            </div>
            <div className="text-center p-4 bg-primary/10 rounded-lg">
              <p className="text-sm text-muted-foreground">Third (100%)</p>
              <p className="text-xl font-bold text-primary">{displayWeight(attempts.third, unit)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
