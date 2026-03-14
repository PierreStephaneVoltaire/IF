import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Sex } from '@powerlifting/types'

export type Unit = 'kg' | 'lb'

interface SettingsState {
  unit: Unit
  barWeightKg: number
  sex: Sex

  // Actions
  toggleUnit: () => void
  setBarWeight: (kg: number) => void
  setSex: (sex: Sex) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      unit: 'kg',
      barWeightKg: 20,
      sex: 'male',

      toggleUnit: () =>
        set((s) => ({ unit: s.unit === 'kg' ? 'lb' : 'kg' })),

      setBarWeight: (kg) => set({ barWeightKg: kg }),

      setSex: (sex) => set({ sex }),
    }),
    { name: 'pl-settings' }
  )
)
