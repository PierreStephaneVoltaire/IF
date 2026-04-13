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
  const resolved = theme === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : theme

  // Toggle .dark class for Tailwind compatibility during migration
  if (resolved === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }

  // Set Mantine color scheme attribute
  root.setAttribute('data-mantine-color-scheme', resolved)
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
