import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3003'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response types
export interface ApiResponse<T> {
  data: T
  error?: string
}

export interface WriteEntryResponse {
  ok: true
  entry_count: number
}

export interface EntryCountResponse {
  count: number
}

// API functions
export async function writeEntry(content: string): Promise<ApiResponse<WriteEntryResponse>> {
  const response = await api.post<ApiResponse<WriteEntryResponse>>('/api/entries', {
    content,
  })
  return response.data
}

export async function getLatestSignal<T>(): Promise<ApiResponse<T | null>> {
  const response = await api.get<ApiResponse<T | null>>('/api/signals/latest')
  return response.data
}

export async function getSignalHistory<T>(days: number = 90): Promise<ApiResponse<T[]>> {
  const response = await api.get<ApiResponse<T[]>>('/api/signals', {
    params: { days },
  })
  return response.data
}

export async function getEntryCount(): Promise<ApiResponse<EntryCountResponse>> {
  const response = await api.get<ApiResponse<EntryCountResponse>>('/api/signals/entry-count')
  return response.data
}
