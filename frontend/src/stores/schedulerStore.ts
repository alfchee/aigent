import { defineStore } from 'pinia'

import { fetchJson } from '../lib/api'

export type SchedulerTrigger = {
  type: 'date' | 'interval' | 'cron' | 'unknown'
  run_date?: string | null
  seconds?: number
  fields?: Record<string, string>
  repr?: string
}

export type SchedulerJob = {
  id: string
  name: string
  prompt: string
  session_id: string
  use_react_loop: boolean
  max_iterations: number
  next_run_time: string | null
  last_run_time: string | null
  trigger: SchedulerTrigger
  paused: boolean
}

export type SchedulerLog = {
  job_id: string | null
  prompt: string
  session_id: string
  use_react_loop: boolean
  max_iterations: number
  status: string
  response: string
  error: string
  started_at: string
  finished_at: string
  duration_seconds: number
}

type DebounceState = {
  timer: number | null
  lastAt: number
  pending: Promise<void> | null
  inFlight: Promise<void> | null
}

type StoreDebounce = {
  jobs: DebounceState
  logs: DebounceState
}

const debounceMap = new WeakMap<object, StoreDebounce>()

const baseDebounceMs = 500
const baseRetryMs = 300
const maxRetries = 3
const isDev = (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV

function getDebounce(store: object): StoreDebounce {
  const existing = debounceMap.get(store)
  if (existing) return existing
  const state: StoreDebounce = {
    jobs: { timer: null, lastAt: 0, pending: null, inFlight: null },
    logs: { timer: null, lastAt: 0, pending: null, inFlight: null }
  }
  debounceMap.set(store, state)
  return state
}

// Stable stringify avoids key-order noise so we only update when payloads truly differ.
function stableStringify(value: unknown): string {
  if (value === null || value === undefined) return String(value)
  if (typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`
  }
  const obj = value as Record<string, unknown>
  const keys = Object.keys(obj).sort()
  const entries = keys.map((key) => `${JSON.stringify(key)}:${stableStringify(obj[key])}`)
  return `{${entries.join(',')}}`
}

// Hash is derived from stable string output to prevent unnecessary state replacements.
function hashPayload(value: unknown): string {
  return stableStringify(value)
}

async function withRetry<T>(fn: () => Promise<T>): Promise<T> {
  let lastError: unknown
  for (let attempt = 0; attempt < maxRetries; attempt += 1) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      const delay = baseRetryMs * Math.pow(2, attempt)
      await new Promise((resolve) => setTimeout(resolve, delay))
    }
  }
  throw lastError
}

// Debounce enforces a minimum interval between network updates to avoid UI blinking.
async function scheduleDebounced(store: object, key: keyof StoreDebounce, task: () => Promise<void>): Promise<void> {
  const debounce = getDebounce(store)[key]
  const now = Date.now()
  const wait = Math.max(0, baseDebounceMs - (now - debounce.lastAt))
  if (now - debounce.lastAt < baseDebounceMs) {
    return debounce.pending || debounce.inFlight || Promise.resolve()
  }
  if (debounce.timer !== null && debounce.pending) {
    return debounce.pending
  }
  if (wait === 0 && debounce.timer === null) {
    debounce.lastAt = now
    debounce.inFlight = task()
      .catch(() => undefined)
      .finally(() => {
        debounce.inFlight = null
      })
    return debounce.inFlight
  }
  debounce.pending = new Promise((resolve, reject) => {
    debounce.timer = window.setTimeout(async () => {
      debounce.timer = null
      debounce.lastAt = Date.now()
      try {
        debounce.inFlight = task()
        await debounce.inFlight
        resolve()
      } catch (error) {
        reject(error)
      } finally {
        debounce.inFlight = null
        debounce.pending = null
      }
    }, wait)
  })
  return debounce.pending
}

export const useSchedulerStore = defineStore('scheduler', {
  state: () => ({
    jobs: [] as SchedulerJob[],
    logs: [] as SchedulerLog[],
    isLoading: false,
    jobsSectionLoading: false,
    logsSectionLoading: false,
    lastUpdated: null as string | null,
    hasChanges: false,
    error: null as string | null,
    _jobsHash: '' as string,
    _logsHash: '' as string
  }),
  getters: {
    activeJobs: (state) => state.jobs.filter((job) => !job.paused),
    pausedJobs: (state) => state.jobs.filter((job) => job.paused),
    jobsByStatus: (state) => (status: 'active' | 'paused' | 'all') => {
      if (status === 'active') return state.jobs.filter((job) => !job.paused)
      if (status === 'paused') return state.jobs.filter((job) => job.paused)
      return state.jobs
    },
    logsByStatus: (state) => (status: string) => state.logs.filter((log) => log.status === status),
    logsSince: (state) => (isoDate: string) => state.logs.filter((log) => log.started_at >= isoDate),
    stats: (state) => {
      const total = state.jobs.length
      const active = state.jobs.filter((job) => !job.paused).length
      const paused = total - active
      const lastRun = state.logs.length ? state.logs[state.logs.length - 1].finished_at : null
      const errorCount = state.logs.filter((log) => log.status !== 'success').length
      return {
        totalJobs: total,
        activeJobs: active,
        pausedJobs: paused,
        lastRunAt: lastRun,
        errorRate: total > 0 ? Number((errorCount / Math.max(1, state.logs.length)).toFixed(3)) : 0
      }
    }
  },
  actions: {
    async fetchJobs() {
      await scheduleDebounced(this, 'jobs', async () => {
        this.jobsSectionLoading = true
        this.isLoading = true
        this.error = null
        try {
          const data = await withRetry(() => fetchJson<SchedulerJob[]>('/api/scheduler/jobs'))
          const nextHash = hashPayload(data)
          if (nextHash !== this._jobsHash) {
            this.jobs = data
            this._jobsHash = nextHash
            this.hasChanges = true
            this.lastUpdated = new Date().toISOString()
            if (isDev) {
              console.debug('[scheduler] jobs updated')
            }
          } else {
            this.hasChanges = false
            if (isDev) {
              console.debug('[scheduler] jobs unchanged')
            }
          }
        } catch (e: any) {
          this.error = e.message || 'Error fetching scheduler jobs'
        } finally {
          this.jobsSectionLoading = false
          this.isLoading = this.logsSectionLoading
        }
      })
    },
    async fetchLogs(jobId?: string) {
      await scheduleDebounced(this, 'logs', async () => {
        this.logsSectionLoading = true
        this.isLoading = true
        this.error = null
        try {
          const url = jobId ? `/api/scheduler/logs?job_id=${encodeURIComponent(jobId)}` : '/api/scheduler/logs'
          const data = await withRetry(() => fetchJson<SchedulerLog[]>(url))
          const nextHash = hashPayload(data)
          if (nextHash !== this._logsHash) {
            this.logs = data
            this._logsHash = nextHash
            this.hasChanges = true
            this.lastUpdated = new Date().toISOString()
            if (isDev) {
              console.debug('[scheduler] logs updated')
            }
          } else {
            this.hasChanges = false
            if (isDev) {
              console.debug('[scheduler] logs unchanged')
            }
          }
        } catch (e: any) {
          this.error = e.message || 'Error fetching scheduler logs'
        } finally {
          this.logsSectionLoading = false
          this.isLoading = this.jobsSectionLoading
        }
      })
    },
    async pauseJob(jobId: string) {
      await fetchJson(`/api/scheduler/jobs/${jobId}/pause`, { method: 'POST' })
      await this.fetchJobs()
    },
    async resumeJob(jobId: string) {
      await fetchJson(`/api/scheduler/jobs/${jobId}/resume`, { method: 'POST' })
      await this.fetchJobs()
    },
    async deleteJob(jobId: string) {
      await fetchJson(`/api/scheduler/jobs/${jobId}`, { method: 'DELETE' })
      await this.fetchJobs()
    }
  }
})
