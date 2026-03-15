import { create } from 'zustand'
import type { DiarySignal } from '@diary-portal/types'
import { getLatestSignal, getSignalHistory, getEntryCount, writeEntry } from '../api/client'

interface DiaryState {
  currentSignal: DiarySignal | null
  signalHistory: DiarySignal[]
  entryCount: number
  loading: boolean
  error: string | null
  submitSuccess: boolean

  // Actions
  fetchLatestSignal: () => Promise<void>
  fetchSignalHistory: (days?: number) => Promise<void>
  fetchEntryCount: () => Promise<void>
  submitEntry: (content: string) => Promise<{ ok: boolean; entry_count: number }>
  clearError: () => void
}

export const useDiaryStore = create<DiaryState>((set) => ({
  currentSignal: null,
  signalHistory: [],
  entryCount: 0,
  loading: false,
  error: null,
  submitSuccess: false,

  fetchLatestSignal: async () => {
    try {
      set({ loading: true, error: null })
      const response = await getLatestSignal<DiarySignal>()

      if (response.error) {
        set({ error: response.error, loading: false })
        return
      }

      set({ currentSignal: response.data, loading: false })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch signal',
        loading: false,
      })
    }
  },

  fetchSignalHistory: async (days = 90) => {
    try {
      set({ loading: true, error: null })
      const response = await getSignalHistory<DiarySignal>(days)

      if (response.error) {
        set({ error: response.error, loading: false })
        return
      }

      set({ signalHistory: response.data, loading: false })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch history',
        loading: false,
      })
    }
  },

  fetchEntryCount: async () => {
    try {
      const response = await getEntryCount()

      if (response.error) {
        console.error('Failed to fetch entry count:', response.error)
        return
      }

      set({ entryCount: response.data?.count || 0 })
    } catch (err) {
      console.error('Failed to fetch entry count:', err)
    }
  },

  submitEntry: async (content: string) => {
    try {
      set({ loading: true, error: null, submitSuccess: false })
      const response = await writeEntry(content)

      if (response.error) {
        set({ error: response.error, loading: false })
        return { ok: false, entry_count: 0 }
      }

      // Update entry count from response
      const entryCount = response.data?.entry_count || 0
      set({ entryCount, loading: false, submitSuccess: true })

      // Clear success message after 3 seconds
      setTimeout(() => set({ submitSuccess: false }), 3000)

      return { ok: true, entry_count: entryCount }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to submit entry',
        loading: false,
      })
      return { ok: false, entry_count: 0 }
    }
  },

  clearError: () => set({ error: null }),
}))
