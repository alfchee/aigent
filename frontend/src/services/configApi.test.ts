import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fetchSoulPrompt, updateSoulPrompt } from './configApi'

describe('configApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fetchSoulPrompt returns soul string on success', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok', soul: 'I am NaviBot' }),
    } as Response)

    const res = await fetchSoulPrompt()
    expect(res).toBe('I am NaviBot')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/config/soul'),
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('fetchSoulPrompt throws error on failure', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response)

    await expect(fetchSoulPrompt()).rejects.toThrow('Failed to fetch soul prompt: 500')
  })

  it('updateSoulPrompt returns new soul string on success', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'ok', soul: 'Updated NaviBot' }),
    } as Response)

    const res = await updateSoulPrompt('Updated NaviBot')
    expect(res).toBe('Updated NaviBot')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/config/soul'),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ soul: 'Updated NaviBot' }),
      }),
    )
  })

  it('updateSoulPrompt throws error on failure', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 400,
    } as Response)

    await expect(updateSoulPrompt('bad')).rejects.toThrow(
      'Failed to update soul prompt: 400',
    )
  })
})
