import {
  mapBackendMessageToChat,
  type BackendChatMessageDto,
} from '@/services/chatMapper'
import type { ChatMessage } from '@/types/chat'

type ListChatMessagesResponse = {
  status: string
  session_id: string
  count: number
  items: BackendChatMessageDto[]
}

function getApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit && explicit.startsWith('http')) return explicit.replace(/\/+$/, '')
  return location.origin
}

function buildUrl(path: string, params?: Record<string, string | number | undefined>) {
  const url = new URL(path, `${getApiBaseUrl()}/`)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined) continue
      url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

export async function fetchChatMessages(params: {
  sessionId: string
  conversationId?: string
  beforeCreatedAt?: number
  limit?: number
}): Promise<ChatMessage[]> {
  const url = buildUrl(`/chat/${encodeURIComponent(params.sessionId)}/messages`, {
    conversationId: params.conversationId,
    beforeCreatedAt: params.beforeCreatedAt,
    limit: params.limit ?? 50,
  })
  const response = await fetch(url, { method: 'GET' })
  if (!response.ok) {
    throw new Error(`chat_messages_http_${response.status}`)
  }
  const data = (await response.json()) as ListChatMessagesResponse
  return (data.items ?? []).map(mapBackendMessageToChat)
}
