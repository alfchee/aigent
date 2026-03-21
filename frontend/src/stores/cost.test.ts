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

  it('merges sessions without deleting existing ones on upsertSessions', async () => {
    // Primera carga
    vi.mocked(fetchCostSummary).mockResolvedValueOnce({
      status: 'ok',
      sessions: [
        {
          session_id: 'sess_1',
          user_id: 'u1',
          total_calls: 1,
          total_input_tokens: 100,
          total_output_tokens: 50,
          total_cost_usd: 0.01,
          daily_limit_usd: 10,
          remaining_budget_usd: 9.99,
          budget_exceeded: false,
          last_call_at: '2026-03-20T10:00:00Z',
        },
      ],
    })

    const store = useCostStore()
    await store.loadSummary()

    expect(store.allSessions).toHaveLength(1)
    expect(store.summariesBySession['sess_1']).toBeDefined()

    // Segunda carga que devuelve array vacío (no debe borrar)
    vi.mocked(fetchCostSummary).mockResolvedValueOnce({
      status: 'ok',
      sessions: [],
    })

    await store.loadSummary()

    // Debería mantener la sesión anterior
    expect(store.allSessions).toHaveLength(1)
    expect(store.summariesBySession['sess_1']).toBeDefined()
  })

  it('prevents race conditions when loadSummary is called multiple times', async () => {
    const store = useCostStore()

    // Simulamos que la primera petición (más antigua) tarda mucho
    const slowResponse = new Promise<any>((resolve) => {
      setTimeout(() => {
        resolve({
          status: 'ok',
          sessions: [
            {
              session_id: 'sess_slow',
              user_id: 'u1',
              total_calls: 1,
              total_input_tokens: 100,
              total_output_tokens: 50,
              total_cost_usd: 0.01,
              daily_limit_usd: 10,
              remaining_budget_usd: 9.99,
              budget_exceeded: false,
              last_call_at: '2026-03-20T10:00:00Z',
            },
          ],
        })
      }, 50)
    })

    // Simulamos que la segunda petición (más nueva) es rápida
    const fastResponse = Promise.resolve({
      status: 'ok',
      sessions: [
        {
          session_id: 'sess_fast',
          user_id: 'u1',
          total_calls: 2,
          total_input_tokens: 200,
          total_output_tokens: 100,
          total_cost_usd: 0.02,
          daily_limit_usd: 10,
          remaining_budget_usd: 9.98,
          budget_exceeded: false,
          last_call_at: '2026-03-20T10:01:00Z',
        },
      ],
    })

    vi.mocked(fetchCostSummary)
      .mockImplementationOnce(() => slowResponse)
      .mockImplementationOnce(() => fastResponse)

    // Disparamos ambas peticiones casi simultáneamente
    const p1 = store.loadSummary()
    const p2 = store.loadSummary()

    await Promise.all([p1, p2])

    // El resultado final debería reflejar solo sess_fast porque sess_slow fue cancelada/ignorada por race condition
    expect(store.summariesBySession['sess_slow']).toBeUndefined()
    expect(store.summariesBySession['sess_fast']).toBeDefined()
    expect(store.loading).toBe(false)
  })
})
