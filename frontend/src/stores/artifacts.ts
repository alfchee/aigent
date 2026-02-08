import { defineStore } from 'pinia'
import { useDebounceFn } from '@vueuse/core'

import { fetchJson } from '../lib/api'
import { bus } from '../lib/bus'

export type ArtifactFileEntry = {
  path: string
  size_bytes: number
  modified_at: string
  mime_type: string | null
}

export type ArtifactListResponse = {
  session_id: string
  files: ArtifactFileEntry[]
}

type Toast = {
  id: string
  message: string
}

export const useArtifactsStore = defineStore('artifacts', {
  state: () => ({
    sessionId: 'default' as string,
    files: [] as ArtifactFileEntry[],
    selectedPath: null as string | null,
    loading: false as boolean,
    error: null as string | null,
    unreadCount: 0 as number,
    toasts: [] as Toast[],
    _eventSource: null as EventSource | null
  }),
  actions: {
    setSessionId(sessionId: string) {
      this.sessionId = sessionId || 'default'
    },
    async fetchArtifacts() {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson<ArtifactListResponse>(`/api/files/${encodeURIComponent(this.sessionId)}`)
        this.files = data.files
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      } finally {
        this.loading = false
      }
    },
    selectArtifact(path: string) {
      this.selectedPath = path
      this.unreadCount = 0
    },
    connectSse() {
      this.disconnectSse()
      const url = `/api/artifacts/events?session_id=${encodeURIComponent(this.sessionId)}`
      const es = new EventSource(url)
      this._eventSource = es

      const debouncedRefresh = useDebounceFn(() => this.fetchArtifacts(), 200)

      es.addEventListener('artifact', (evt) => {
        try {
          const data = JSON.parse((evt as MessageEvent).data) as { path?: string }
          this.unreadCount += 1
          const msg = data.path ? `Nuevo artefacto: ${data.path}` : 'Nuevo artefacto'
          const toast = { id: `${Date.now()}_${Math.random()}`, message: msg }
          this.toasts.push(toast)
          bus.emit('toast:push', toast)
          bus.emit('artifact:event', data as any)
          window.setTimeout(() => this.popToast(toast.id), 4500)
        } catch {
          this.unreadCount += 1
        } finally {
          debouncedRefresh()
        }
      })

      es.addEventListener('error', () => {
        this.error = 'Conexión SSE falló. Reintentando…'
      })
    },
    disconnectSse() {
      if (this._eventSource) {
        this._eventSource.close()
        this._eventSource = null
      }
    },
    popToast(id: string) {
      this.toasts = this.toasts.filter((t) => t.id !== id)
    }
  }
})
