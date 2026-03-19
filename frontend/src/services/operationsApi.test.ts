import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchTechnicalPanelData } from '@/services/operationsApi'

describe('operationsApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('carga métricas y roles para panel técnico', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'ok',
          metrics: {
            global: {
              total_runs: 10,
              success_runs: 8,
              policy_violations: 1,
              timeouts: 1,
              execution_errors: 0,
              total_duration_ms: 500,
              avg_duration_ms: 50,
            },
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'ok',
          config_path: '/workspace/config/roles.json',
          updated_at: 12345,
          supervisor: { name: 'Supervisor', description: '', system_prompt: '' },
          workers: [
            {
              id: 'coder',
              name: 'Coder',
              description: '',
              system_prompt: '',
              skills: ['python'],
            },
          ],
        }),
      })
    vi.stubGlobal('fetch', fetchMock)

    const data = await fetchTechnicalPanelData()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(data.roles.workerCount).toBe(1)
    expect(data.roles.workers[0].id).toBe('coder')
    expect(data.metrics.global.total_runs).toBe(10)
  })

  it('lanza error si falla alguna llamada', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    })
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchTechnicalPanelData()).rejects.toThrow('operations_http_500')
  })
})
