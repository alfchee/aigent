import { defineStore } from 'pinia'

import { fetchJson } from '../lib/api'

export type SessionListItem = {
  id: string
  title: string
  created_at: string | null
  updated_at: string | null
}

type ListSessionsResponse = {
  sessions: SessionListItem[]
}

type CreateSessionResponse = {
  id: string
}

type AutotitleResponse = {
  id: string
  title: string
}

export const useSessionsStore = defineStore('sessions', {
  state: () => ({
    sessions: [] as SessionListItem[],
    loading: false as boolean,
    error: null as string | null
  }),
  actions: {
    async fetchSessions() {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson<ListSessionsResponse>('/api/sessions')
        this.sessions = data.sessions || []
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      } finally {
        this.loading = false
      }
    },
    async createSession(id: string, title?: string) {
      const payload = { id, title }
      const data = await fetchJson<CreateSessionResponse>('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      await this.fetchSessions()
      return data.id
    },
    async deleteSession(id: string) {
      await fetchJson(`/api/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' })
      await this.fetchSessions()
    },
    async updateTitle(id: string, title: string) {
      await fetchJson(`/api/sessions/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      })
      await this.fetchSessions()
    },
    async autotitle(id: string) {
      const data = await fetchJson<AutotitleResponse>(`/api/sessions/${encodeURIComponent(id)}/autotitle`, {
        method: 'POST'
      })
      await this.fetchSessions()
      return data.title
    }
  }
})

