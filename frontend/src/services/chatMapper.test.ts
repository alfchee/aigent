import { describe, expect, it } from 'vitest'
import { mapBackendMessageToChat } from '@/services/chatMapper'

describe('chatMapper', () => {
  it('mapea DTO backend a ChatMessage frontend', () => {
    const mapped = mapBackendMessageToChat({
      id: 'm1',
      session_id: 's1',
      conversation_id: 'c1',
      role: 'assistant',
      text: 'hola',
      created_at: 123456,
      meta: { source: 'ws' },
    })
    expect(mapped).toEqual({
      id: 'm1',
      conversationId: 'c1',
      role: 'assistant',
      text: 'hola',
      createdAt: 123456,
      status: 'delivered',
      meta: { source: 'ws' },
    })
  })
})
