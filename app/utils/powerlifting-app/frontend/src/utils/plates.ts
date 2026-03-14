import { KG_PLATES, LB_PLATES, KG_PLATE_COLORS, LB_PLATE_COLORS } from '@/constants/plates'
import type { PlateLoadout } from '@powerlifting/types'
import { kgToLb, lbToKg } from './units'

/**
 * Calculate the plate loadout for a target weight using a greedy algorithm.
 * All weights are in kg internally.
 */
export function getPlateLoadout(
  targetKg: number,
  barKg: number = 20,
  plates: readonly number[] = KG_PLATES
): PlateLoadout {
  const perSide = (targetKg - barKg) / 2

  if (perSide < 0) {
    return { plates: [], totalKg: barKg, perSideKg: 0, remainder: perSide, achievable: false }
  }

  const sorted = [...plates].sort((a, b) => b - a)
  const result: number[] = []
  let remaining = perSide

  for (const plate of sorted) {
    while (remaining >= plate - 0.0001) {
      result.push(plate)
      remaining = parseFloat((remaining - plate).toFixed(4))
    }
  }

  const perSideLoaded = result.reduce((s, p) => s + p, 0)
  return {
    plates: result,
    totalKg: parseFloat((barKg + perSideLoaded * 2).toFixed(4)),
    perSideKg: perSideLoaded,
    remainder: remaining,
    achievable: remaining < 0.001,
  }
}

/**
 * Find the closest achievable weight using lb plates.
 * Returns both kg and lb values.
 */
export function closestLbLoadout(
  targetKg: number,
  barKg: number = 20
): {
  loadout: PlateLoadout
  targetLb: number
  achievedLb: number
  achievedKg: number
  deltaKg: number
} {
  const targetLb = kgToLb(targetKg)
  // Convert lb plates to kg for the greedy algorithm
  const lbPlatesAsKg = LB_PLATES.map(lbToKg)
  const loadout = getPlateLoadout(targetKg, barKg, lbPlatesAsKg)

  return {
    loadout,
    targetLb,
    achievedLb: kgToLb(loadout.totalKg),
    achievedKg: loadout.totalKg,
    deltaKg: parseFloat((loadout.totalKg - targetKg).toFixed(2)),
  }
}

/**
 * Get the color for a plate by denomination.
 */
export function getPlateColor(plateKg: number, unit: 'kg' | 'lb' = 'kg'): string {
  if (unit === 'lb') {
    // Convert back to lb to look up color
    const lbPlate = Math.round(kgToLb(plateKg))
    return LB_PLATE_COLORS[lbPlate] || '#6b7280'
  }
  return KG_PLATE_COLORS[plateKg] || '#6b7280'
}

/**
 * Calculate competition attempt suggestions.
 */
export function compAttempts(targetKg: number): {
  opener: number
  second: number
  third: number
} {
  return {
    opener: roundToNearest(targetKg * 0.92, 2.5),
    second: roundToNearest(targetKg * 0.96, 2.5),
    third: targetKg,
  }
}

/**
 * Round to nearest increment (default 2.5kg).
 */
function roundToNearest(value: number, increment: number = 2.5): number {
  return Math.round(value / increment) * increment
}
