import { describe, expect, it, vi } from 'vitest'

import { initPinia } from '../test/utils'
import { useSessionsStore } from './sessions'

vi.mock('../lib/api', () => ({
  fetchJson: vi.fn(),
}))

describe('sessions store', () => {
  it('fetches sessions list', async () => {
    initPinia()
    const store = useSessionsStore()
    const { fetchJson } = await import('../lib/api')

    ;(fetchJson as any).mockResolvedValue({
      sessions: [{ id: 's1', title: 'Hola', created_at: null, updated_at: null }],
    })

    await store.fetchSessions()
    expect(store.sessions.length).toBe(1)
    expect(store.sessions[0].id).toBe('s1')
  })

  it('creates session and refreshes list', async () => {
    initPinia()
    const store = useSessionsStore()
    const { fetchJson } = await import('../lib/api')

    ;(fetchJson as any).mockResolvedValueOnce({ id: 's_new' }).mockResolvedValueOnce({
      sessions: [{ id: 's_new', title: 'Nueva Conversación', created_at: null, updated_at: null }],
    })

    const id = await store.createSession('s_new')
    expect(id).toBe('s_new')
    expect(store.sessions[0].id).toBe('s_new')
  })
})
