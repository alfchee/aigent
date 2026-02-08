import { describe, expect, it, vi } from 'vitest'

import { initPinia } from '../test/utils'
import { useChatStore } from './chat'

vi.mock('../lib/api', () => ({
  fetchJson: vi.fn()
}))

describe('chat store history', () => {
  it('loads initial session history in chronological order', async () => {
    initPinia()
    const store = useChatStore()
    const { fetchJson } = await import('../lib/api')

    ;(fetchJson as any).mockResolvedValue({
      session_id: 's1',
      items: [
        { id: 1, role: 'user', content: 'hola', created_at: '2026-01-01T00:00:00Z' },
        { id: 2, role: 'assistant', content: 'ok', created_at: '2026-01-01T00:00:01Z' }
      ],
      has_more: false,
      next_before_id: 1,
      limit: 50
    })

    await store.loadSessionHistory('s1')
    expect(store.messages.length).toBe(2)
    expect(store.messages[0].content).toBe('hola')
    expect(store.messages[1].content).toBe('ok')
    expect(store.historyHasMore).toBe(false)
  })

  it('prepends older messages when loading more history', async () => {
    initPinia()
    const store = useChatStore()
    const { fetchJson } = await import('../lib/api')

    ;(fetchJson as any)
      .mockResolvedValueOnce({
        session_id: 's1',
        items: [
          { id: 101, role: 'user', content: 'u1', created_at: null },
          { id: 102, role: 'assistant', content: 'a1', created_at: null }
        ],
        has_more: true,
        next_before_id: 101,
        limit: 50
      })
      .mockResolvedValueOnce({
        session_id: 's1',
        items: [
          { id: 99, role: 'user', content: 'u0', created_at: null },
          { id: 100, role: 'assistant', content: 'a0', created_at: null }
        ],
        has_more: false,
        next_before_id: 99,
        limit: 50
      })

    await store.loadSessionHistory('s1')
    await store.loadMoreHistory('s1')

    expect(store.messages.map((m) => m.id)).toEqual([99, 100, 101, 102])
    expect(store.historyHasMore).toBe(false)
  })
})

