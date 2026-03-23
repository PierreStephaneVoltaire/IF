import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Sex } from '@powerlifting/types'

export type Unit = 'kg' | 'lb'
export type Theme = 'light' | 'dark' | 'system'

interface SettingsState {
  unit: Unit
  barWeightKg: number
  sex: Sex
  theme: Theme

  // Actions
  toggleUnit: () => void
  setBarWeight: (kg: number) => void
  setSex: (sex: Sex) => void
  setTheme: (theme: Theme) => void
}

function applyTheme(theme: Theme) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else if (theme === 'light') {
    root.classList.remove('dark')
  } else {
    // System preference
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      unit: 'kg',
      barWeightKg: 20,
      sex: 'male',
      theme: 'system',

      toggleUnit: () =>
        set((s) => ({ unit: s.unit === 'kg' ? 'lb' : 'kg' })),

      setBarWeight: (kg) => set({ barWeightKg: kg }),

      setSex: (sex) => set({ sex }),

      setTheme: (theme) => {
        applyTheme(theme)
        set({ theme })
      },
    }),
    {
      name: 'pl-settings',
      onRehydrateStorage: () => (state) => {
        // Apply theme on load
        if (state?.theme) {
          applyTheme(state.theme)
        }
      },
    }
  )
)
