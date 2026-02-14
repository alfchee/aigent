import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSchedulerStore } from './schedulerStore'

vi.mock('../lib/api', () => ({
  fetchJson: vi.fn()
}))

const jobsPayload = [
  {
    id: 'job-1',
    name: 'Job Uno',
    prompt: 'Test',
    session_id: 'default',
    use_react_loop: true,
    max_iterations: 10,
    next_run_time: null,
    last_run_time: null,
    trigger: { type: 'interval', seconds: 60 },
    paused: false
  }
]

const logsPayload = [
  {
    job_id: 'job-1',
    prompt: 'Test',
    session_id: 'default',
    use_react_loop: true,
    max_iterations: 10,
    status: 'success',
    response: 'ok',
    error: '',
    started_at: '2026-02-13T23:00:00Z',
    finished_at: '2026-02-13T23:00:02Z',
    duration_seconds: 2
  }
]

describe('scheduler store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-14T00:00:00Z'))
  })

  it('actualiza jobs solo cuando hay cambios reales', async () => {
    const { fetchJson } = await import('../lib/api')
    ;(fetchJson as any).mockResolvedValueOnce(jobsPayload).mockResolvedValueOnce(jobsPayload)

    const store = useSchedulerStore()
    const first = store.fetchJobs()
    await vi.advanceTimersByTimeAsync(500)
    await first

    expect(store.jobs.length).toBe(1)
    expect(store.hasChanges).toBe(true)

    vi.setSystemTime(new Date('2026-02-14T00:00:02Z'))
    const second = store.fetchJobs()
    await vi.advanceTimersByTimeAsync(500)
    await second

    expect(store.jobs.length).toBe(1)
    expect(store.hasChanges).toBe(false)
  })

  it('evita múltiples llamadas cuando las peticiones son frecuentes', async () => {
    const { fetchJson } = await import('../lib/api')
    ;(fetchJson as any).mockResolvedValue(jobsPayload)

    const store = useSchedulerStore()
    const first = store.fetchJobs()
    const second = store.fetchJobs()
    await vi.advanceTimersByTimeAsync(500)
    await Promise.all([first, second])

    expect((fetchJson as any).mock.calls.length).toBe(1)
  })

  it('no actualiza logs si el payload es idéntico', async () => {
    const { fetchJson } = await import('../lib/api')
    ;(fetchJson as any).mockResolvedValueOnce(logsPayload).mockResolvedValueOnce(logsPayload)

    const store = useSchedulerStore()
    const first = store.fetchLogs()
    await vi.advanceTimersByTimeAsync(500)
    await first

    expect(store.logs.length).toBe(1)
    expect(store.hasChanges).toBe(true)

    vi.setSystemTime(new Date('2026-02-14T00:00:02Z'))
    const second = store.fetchLogs()
    await vi.advanceTimersByTimeAsync(500)
    await second

    expect(store.logs.length).toBe(1)
    expect(store.hasChanges).toBe(false)
  })
})
