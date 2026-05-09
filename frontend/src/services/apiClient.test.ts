import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getStoredApiKey,
  setStoredApiKey,
  clearStoredApiKey,
  hasApiKey,
  authFetch,
  buildWsUrl,
} from '@/services/apiClient'

const STORAGE_KEY = 'aigent_api_key'

describe('apiClient', () => {
  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  // ---------------------------------------------------------------------------
  // localStorage helpers
  // ---------------------------------------------------------------------------

  describe('getStoredApiKey / setStoredApiKey / clearStoredApiKey', () => {
    it('returns empty string when nothing stored', () => {
      expect(getStoredApiKey()).toBe('')
    })

    it('returns the stored key after setStoredApiKey', () => {
      setStoredApiKey('my-secret')
      expect(getStoredApiKey()).toBe('my-secret')
      expect(localStorage.getItem(STORAGE_KEY)).toBe('my-secret')
    })

    it('clears the key', () => {
      setStoredApiKey('my-secret')
      clearStoredApiKey()
      expect(getStoredApiKey()).toBe('')
    })
  })

  describe('hasApiKey', () => {
    it('returns false when no key stored', () => {
      expect(hasApiKey()).toBe(false)
    })

    it('returns true when a key is stored', () => {
      setStoredApiKey('k')
      expect(hasApiKey()).toBe(true)
    })
  })

  // ---------------------------------------------------------------------------
  // authFetch
  // ---------------------------------------------------------------------------

  describe('authFetch', () => {
    it('sends no Authorization header when no key is stored', async () => {
      const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
      vi.stubGlobal('fetch', fetchMock)

      await authFetch('/api/test')

      const [, init] = fetchMock.mock.calls[0] as [
        string,
        RequestInit & { headers: Headers },
      ]
      expect(new Headers(init.headers).has('Authorization')).toBe(false)
    })

    it('sends Authorization: Bearer header when a key is stored', async () => {
      setStoredApiKey('test-key')
      const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
      vi.stubGlobal('fetch', fetchMock)

      await authFetch('/api/test')

      const [, init] = fetchMock.mock.calls[0] as [
        string,
        RequestInit & { headers: Headers },
      ]
      expect(new Headers(init.headers).get('Authorization')).toBe('Bearer test-key')
    })

    it('merges caller-supplied headers without clobbering them', async () => {
      setStoredApiKey('test-key')
      const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
      vi.stubGlobal('fetch', fetchMock)

      await authFetch('/api/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      const [, init] = fetchMock.mock.calls[0] as [
        string,
        RequestInit & { headers: Headers },
      ]
      const h = new Headers(init.headers)
      expect(h.get('Authorization')).toBe('Bearer test-key')
      expect(h.get('Content-Type')).toBe('application/json')
    })

    it('handles Headers instance as init.headers', async () => {
      setStoredApiKey('test-key')
      const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }))
      vi.stubGlobal('fetch', fetchMock)

      const existing = new Headers({ 'X-Custom': 'value' })
      await authFetch('/api/test', { headers: existing })

      const [, init] = fetchMock.mock.calls[0] as [
        string,
        RequestInit & { headers: Headers },
      ]
      const h = new Headers(init.headers)
      expect(h.get('Authorization')).toBe('Bearer test-key')
      expect(h.get('X-Custom')).toBe('value')
    })
  })

  // ---------------------------------------------------------------------------
  // buildWsUrl
  // ---------------------------------------------------------------------------

  describe('buildWsUrl', () => {
    it('returns the URL unchanged when no key is stored', () => {
      expect(buildWsUrl('ws://host/ws/abc')).toBe('ws://host/ws/abc')
    })

    it('appends ?token= when a key is stored', () => {
      setStoredApiKey('ws-secret')
      expect(buildWsUrl('ws://host/ws/abc')).toBe('ws://host/ws/abc?token=ws-secret')
    })

    it('uses & when the URL already contains a query string', () => {
      setStoredApiKey('ws-secret')
      expect(buildWsUrl('ws://host/ws/abc?foo=bar')).toBe(
        'ws://host/ws/abc?foo=bar&token=ws-secret',
      )
    })

    it('percent-encodes the token', () => {
      setStoredApiKey('key with spaces')
      expect(buildWsUrl('ws://host/ws/abc')).toBe(
        'ws://host/ws/abc?token=key%20with%20spaces',
      )
    })
  })
})
