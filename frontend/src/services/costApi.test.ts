import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  fetchCostSummary,
  formatTokens,
  formatCost,
  formatRelativeTime,
} from '@/services/costApi'

describe('costApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('fetchCostSummary', () => {
    it('fetches global cost summary without session', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: 'ok',
          sessions: [
            {
              session_id: 'sess_1',
              user_id: 'u1',
              total_calls: 5,
              total_input_tokens: 1000,
              total_output_tokens: 500,
              total_cost_usd: 0.0125,
              daily_limit_usd: 10.0,
              remaining_budget_usd: 9.9875,
              budget_exceeded: false,
              last_call_at: '2026-03-20T10:00:00Z',
            },
          ],
          total_cost_usd: 0.0125,
        }),
      })
      vi.stubGlobal('fetch', fetchMock)

      const data = await fetchCostSummary()
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(data.status).toBe('ok')
      expect(data.sessions).toHaveLength(1)
      expect(data.sessions![0].session_id).toBe('sess_1')
    })

    it('fetches cost summary for specific session', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: 'ok',
          session_id: 'sess_abc',
          user_id: 'u1',
          total_calls: 3,
          total_input_tokens: 500,
          total_output_tokens: 250,
          total_cost_usd: 0.00625,
          daily_limit_usd: 10.0,
          remaining_budget_usd: 9.99375,
          budget_exceeded: false,
          last_call_at: '2026-03-20T11:00:00Z',
        }),
      })
      vi.stubGlobal('fetch', fetchMock)

      const data = await fetchCostSummary('sess_abc')
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('session_id=sess_abc'),
        expect.any(Object),
      )
      expect(data.session_id).toBe('sess_abc')
    })

    it('throws error on HTTP failure', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      })
      vi.stubGlobal('fetch', fetchMock)

      await expect(fetchCostSummary()).rejects.toThrow('500 Internal Server Error')
    })
  })

  describe('formatTokens', () => {
    it('formats tokens in millions', () => {
      expect(formatTokens(1_500_000)).toBe('1.5M')
    })
    it('formats tokens in thousands', () => {
      expect(formatTokens(12_500)).toBe('12.5K')
    })
    it('formats small tokens as-is', () => {
      expect(formatTokens(500)).toBe('500')
    })
  })

  describe('formatCost', () => {
    it('formats cost with 6 decimal places', () => {
      expect(formatCost(0.0125)).toBe('$0.012500')
    })
  })

  describe('formatRelativeTime', () => {
    it('returns "ahora" for recent timestamps', () => {
      const now = new Date().toISOString()
      expect(formatRelativeTime(now)).toBe('ahora')
    })
  })
})
