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

export const useSchedulerStore = defineStore('scheduler', {
  state: () => ({
    jobs: [] as SchedulerJob[],
    logs: [] as SchedulerLog[],
    loading: false,
    error: null as string | null
  }),
  actions: {
    async fetchJobs() {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson<SchedulerJob[]>('/api/scheduler/jobs')
        this.jobs = data
      } catch (e: any) {
        this.error = e.message || 'Error fetching scheduler jobs'
      } finally {
        this.loading = false
      }
    },
    async fetchLogs(jobId?: string) {
      try {
        const url = jobId ? `/api/scheduler/logs?job_id=${encodeURIComponent(jobId)}` : '/api/scheduler/logs'
        const data = await fetchJson<SchedulerLog[]>(url)
        this.logs = data
      } catch (e: any) {
        this.error = e.message || 'Error fetching scheduler logs'
      }
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
