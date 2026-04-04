import { create } from 'zustand'
import type { DiarySignal } from '@diary-portal/types'
import type { DiaryEntry } from '../api/client'
import {
  getLatestSignal,
  getSignalHistory,
  getEntryCount,
  writeEntry,
  getEntries,
  updateEntry as apiUpdateEntry,
  deleteEntry as apiDeleteEntry,
} from '../api/client'

interface DiaryState {
  currentSignal: DiarySignal | null
  signalHistory: DiarySignal[]
  entries: DiaryEntry[]
  entryCount: number
  loading: boolean
  error: string | null
  submitSuccess: boolean

  // Actions
  fetchLatestSignal: () => Promise<void>
  fetchSignalHistory: (days?: number) => Promise<void>
  fetchEntries: () => Promise<void>
  fetchEntryCount: () => Promise<void>
  submitEntry: (content: string) => Promise<{ ok: boolean; entry_count: number }>
  updateEntry: (sk: string, content: string) => Promise<void>
  deleteEntry: (sk: string) => Promise<void>
  clearError: () => void
}

export const useDiaryStore = create<DiaryState>((set) => ({
  currentSignal: null,
  signalHistory: [],
  entries: [],
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

  fetchEntries: async () => {
    try {
      set({ loading: true, error: null })
      const response = await getEntries()

      if (response.error) {
        set({ error: response.error, loading: false })
        return
      }

      set({ entries: response.data, loading: false })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to fetch entries',
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

  updateEntry: async (sk: string, content: string) => {
    try {
      set({ loading: true, error: null })
      const response = await apiUpdateEntry(sk, content)

      if (response.error) {
        set({ error: response.error, loading: false })
        return
      }

      // Update the entry in the list
      set((state) => ({
        entries: state.entries.map((e) => (e.sk === sk ? response.data : e)),
        loading: false,
      }))
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to update entry',
        loading: false,
      })
    }
  },

  deleteEntry: async (sk: string) => {
    try {
      set({ loading: true, error: null })
      const response = await apiDeleteEntry(sk)

      if (response.error) {
        set({ error: response.error, loading: false })
        return
      }

      // Remove the entry from the list
      set((state) => ({
        entries: state.entries.filter((e) => e.sk !== sk),
        entryCount: state.entryCount - 1,
        loading: false,
      }))
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to delete entry',
        loading: false,
      })
    }
  },

  clearError: () => set({ error: null }),
}))
