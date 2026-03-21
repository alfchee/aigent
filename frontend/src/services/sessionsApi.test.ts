import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchSessions } from '@/services/sessionsApi'

describe('sessionsApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('obtiene sesiones remotas', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        count: 1,
        items: [
          {
            session_id: 's1',
            title: 'Conversación 1',
            last_activity: 1000,
            total_messages: 8,
            last_message_preview: 'hola',
            source: 'db',
          },
        ],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const sessions = await fetchSessions()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0][0])).toContain('/sessions')
    expect(sessions[0].session_id).toBe('s1')
    expect(sessions[0].total_messages).toBe(8)
  })

  it('lanza error cuando HTTP falla', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 })
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchSessions()).rejects.toThrow('Failed to fetch sessions: 500')
  })
})
