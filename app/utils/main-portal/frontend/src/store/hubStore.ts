import { create } from 'zustand'
import type { HubStatusResponse } from '../types'
import { fetchHubStatus } from '../api/client'

interface HubState {
  data: HubStatusResponse | null
  loading: boolean
  error: string | null
  fetch: () => Promise<void>
  startPolling: (intervalMs?: number) => void
  stopPolling: () => void
}

let pollingInterval: ReturnType<typeof setInterval> | null = null

export const useHubStore = create<HubState>((set) => ({
  data: null,
  loading: false,
  error: null,

  fetch: async () => {
    set({ loading: true, error: null })
    try {
      const data = await fetchHubStatus()
      set({ data, loading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch',
        loading: false
      })
    }
  },

  startPolling: (intervalMs = 30000) => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
    }
    // Fetch immediately
    useHubStore.getState().fetch()
    // Then poll
    pollingInterval = setInterval(() => {
      useHubStore.getState().fetch()
    }, intervalMs)
  },

  stopPolling: () => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
      pollingInterval = null
    }
  },
}))
