import type { ChatMessage } from '@/types/chat'

export type BackendChatMessageDto = {
  id: string
  session_id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  created_at: number
  meta?: Record<string, unknown>
}

export function mapBackendMessageToChat(dto: BackendChatMessageDto): ChatMessage {
  return {
    id: dto.id,
    conversationId: dto.conversation_id,
    role: dto.role,
    text: dto.text,
    createdAt: dto.created_at,
    status: dto.role === 'user' ? 'sent' : 'delivered',
    meta: dto.meta ?? {},
  }
}
