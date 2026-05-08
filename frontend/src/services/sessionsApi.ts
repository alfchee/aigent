export type SessionSummaryDto = {
  session_id: string
  title: string
  last_activity: number
  total_messages: number
  last_message_preview?: string
  last_conversation_id?: string
  summary?: string | null
  source?: 'db' | 'workspace'
  folder?: string
  agentId?: string
  tags?: string[]
}

type ListSessionsResponseDto = {
  status: string
  count: number
  items: SessionSummaryDto[]
}

function getApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit && explicit.startsWith('http')) return explicit.replace(/\/+$/, '')
  return location.origin
}

function buildUrl(path: string) {
  return new URL(path, `${getApiBaseUrl()}/`).toString()
}

import { authFetch } from '@/services/apiClient'

export async function fetchSessions(): Promise<SessionSummaryDto[]> {
  const response = await authFetch(buildUrl('/sessions'), { method: 'GET' })
  if (!response.ok) {
    throw new Error(`Failed to fetch sessions: ${response.status}`)
  }
  const data = (await response.json()) as ListSessionsResponseDto
  return data.items
}
