import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCostStore } from './cost'
import { fetchCostSummary } from '@/services/costApi'

vi.mock('@/services/costApi', () => ({
  fetchCostSummary: vi.fn(),
}))

describe('cost store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads direct session summary', async () => {
    vi.mocked(fetchCostSummary).mockResolvedValueOnce({
      status: 'ok',
      session_id: 'sess_1',
      user_id: 'u1',
      total_calls: 4,
      total_input_tokens: 1500,
      total_output_tokens: 800,
      total_cost_usd: 0.01,
      daily_limit_usd: 10,
      remaining_budget_usd: 9.99,
      budget_exceeded: false,
      last_call_at: '2026-03-20T10:00:00Z',
    })

    const store = useCostStore()
    await store.loadSummary('sess_1')

    expect(store.currentSessionId).toBe('sess_1')
    expect(store.currentSummary?.total_calls).toBe(4)
  })

  it('falls back to global summaries when requested session is not found', async () => {
    vi.mocked(fetchCostSummary)
      .mockResolvedValueOnce({
        status: 'ok',
        session_id: 'missing',
        not_found: true,
      })
      .mockResolvedValueOnce({
        status: 'ok',
        sessions: [
          {
            session_id: 'sess_a',
            user_id: 'u1',
            total_calls: 3,
            total_input_tokens: 1000,
            total_output_tokens: 600,
            total_cost_usd: 0.012,
            daily_limit_usd: 10,
            remaining_budget_usd: 9.988,
            budget_exceeded: false,
            last_call_at: '2026-03-20T10:01:00Z',
          },
          {
            session_id: 'sess_b',
            user_id: 'u1',
            total_calls: 5,
            total_input_tokens: 2000,
            total_output_tokens: 1200,
            total_cost_usd: 0.022,
            daily_limit_usd: 10,
            remaining_budget_usd: 9.978,
            budget_exceeded: false,
            last_call_at: '2026-03-20T10:05:00Z',
          },
        ],
      })

    const store = useCostStore()
    await store.loadSummary('missing')

    expect(fetchCostSummary).toHaveBeenCalledTimes(2)
    expect(store.currentSessionId).toBe('sess_b')
    expect(store.currentSummary?.total_cost_usd).toBe(0.022)
  })
})
