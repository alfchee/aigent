import { describe, expect, it, vi, afterEach } from 'vitest'
import { fetchJson, NetworkError, TimeoutError, ApiError } from './api'

// Mock global fetch
const fetchMock = vi.fn()
global.fetch = fetchMock

describe('fetchJson', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('should return data on success', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      text: async () => JSON.stringify({ success: true }),
      json: async () => ({ success: true }),
    })

    const data = await fetchJson('/test')
    expect(data).toEqual({ success: true })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('should retry on network error and succeed', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ success: true }),
      json: async () => ({ success: true }),
    })

    const data = await fetchJson('/test', { retries: 2, retryDelay: 10 })
    expect(data).toEqual({ success: true })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('should throw NetworkError after max retries', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(fetchJson('/test', { retries: 2, retryDelay: 10 })).rejects.toThrow(NetworkError)
    expect(fetchMock).toHaveBeenCalledTimes(3) // Initial + 2 retries
  })

  it('should throw TimeoutError on timeout', async () => {
    vi.useFakeTimers()

    fetchMock.mockImplementation(async (_url, options) => {
      const signal = options.signal
      return new Promise((_, reject) => {
        if (signal.aborted) {
          const err = new Error('The user aborted a request.')
          err.name = 'AbortError'
          reject(err)
          return
        }
        signal.addEventListener('abort', () => {
          const err = new Error('The user aborted a request.')
          err.name = 'AbortError'
          reject(err)
        })
      })
    })

    const promise = fetchJson('/test', { timeout: 100, retries: 0 })

    vi.advanceTimersByTime(200)

    await expect(promise).rejects.toThrow(TimeoutError)

    vi.useRealTimers()
  })

  it('should throw ApiError on 4xx/5xx status', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 404,
      text: async () => JSON.stringify({ error: 'Not found' }),
    })

    await expect(fetchJson('/test')).rejects.toThrow(ApiError)
  })

  it('should not retry on ApiError (4xx/5xx)', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => 'Server Error',
    })

    await expect(fetchJson('/test', { retries: 3 })).rejects.toThrow(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
