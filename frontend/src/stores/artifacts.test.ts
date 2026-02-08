import { describe, expect, it, vi } from 'vitest'

import { initPinia } from '../test/utils'
import { useArtifactsStore } from './artifacts'

describe('artifacts store', () => {
  it('increments unreadCount and refreshes on artifact event', async () => {
    initPinia()
    const store = useArtifactsStore()
    store.setSessionId('s1')

    const fetchSpy = vi.spyOn(store, 'fetchArtifacts').mockResolvedValue(undefined as any)
    store.connectSse()

    const es = (store as any)._eventSource
    es.emit('artifact', { path: 'a.txt', op: 'write' })

    expect(store.unreadCount).toBeGreaterThanOrEqual(1)
    await new Promise((r) => setTimeout(r, 250))
    expect(fetchSpy).toHaveBeenCalled()
  })
})

