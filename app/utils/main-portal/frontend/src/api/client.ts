import type { HubStatusResponse } from '../types'

const API_URL = import.meta.env.VITE_API_URL || ''

export async function fetchHubStatus(): Promise<HubStatusResponse> {
  const response = await fetch(`${API_URL}/api/hub/status`)

  if (!response.ok) {
    throw new Error(`Failed to fetch hub status: ${response.status}`)
  }

  const json = await response.json()
  return json.data
}
