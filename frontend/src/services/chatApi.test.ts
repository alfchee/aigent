import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchChatMessages } from '@/services/chatApi'

describe('chatApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('solicita historial y lo devuelve mapeado', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        session_id: 's1',
        count: 1,
        items: [
          {
            id: 'm1',
            session_id: 's1',
            conversation_id: 'c1',
            role: 'user',
            text: 'hola',
            created_at: 1000,
            meta: { source: 'test' },
          },
        ],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const items = await fetchChatMessages({
      sessionId: 's1',
      conversationId: 'c1',
      beforeCreatedAt: 2000,
      limit: 20,
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const calledUrl = String(fetchMock.mock.calls[0][0])
    expect(calledUrl).toContain('/chat/s1/messages')
    expect(calledUrl).toContain('conversationId=c1')
    expect(calledUrl).toContain('beforeCreatedAt=2000')
    expect(calledUrl).toContain('limit=20')
    expect(items[0].conversationId).toBe('c1')
    expect(items[0].createdAt).toBe(1000)
  })

  it('lanza error si HTTP no es exitoso', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 })
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchChatMessages({ sessionId: 's1' })).rejects.toThrow(
      'chat_messages_http_500',
    )
  })
})
