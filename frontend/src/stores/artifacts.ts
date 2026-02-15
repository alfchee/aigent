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

export type ArtifactTrashEntry = {
  trash_id: string
  path: string
  deleted_at: string
  restore_until: string
  size_bytes: number
  actor?: string | null
  reason?: string | null
  expired?: boolean
}

export type ArtifactAuditEntry = {
  op: string
  path?: string
  trash_id?: string
  size_bytes?: number
  actor?: string | null
  reason?: string | null
  restore_until?: string
  restored_at?: string
  timestamp?: string
  count?: number
  freed_bytes?: number
}

type Toast = {
  id: string
  message: string
}

export const useArtifactsStore = defineStore('artifacts', {
  state: () => ({
    sessionId: 'default' as string,
    viewSessionId: 'default' as string,
    viewAllowArchived: false as boolean,
    files: [] as ArtifactFileEntry[],
    trash: [] as ArtifactTrashEntry[],
    audit: [] as ArtifactAuditEntry[],
    selectedPath: null as string | null,
    loading: false as boolean,
    error: null as string | null,
    unreadCount: 0 as number,
    toasts: [] as Toast[],
    _eventSource: null as EventSource | null
  }),
  actions: {
    setSessionId(sessionId: string) {
      const sid = sessionId || 'default'
      this.sessionId = sid
      this.viewSessionId = sid
      this.viewAllowArchived = false
      this.selectedPath = null
    },
    async setViewSession(sessionId: string, allowArchived = false) {
      const sid = sessionId || this.sessionId || 'default'
      this.viewSessionId = sid
      this.viewAllowArchived = Boolean(allowArchived)
      this.selectedPath = null
      await this.fetchArtifacts()
    },
    async fetchArtifacts() {
      this.loading = true
      this.error = null
      try {
        const targetId = this.viewSessionId || this.sessionId
        const params = this.viewAllowArchived ? '?allow_archived=true' : ''
        const data = await fetchJson<ArtifactListResponse>(`/api/files/${encodeURIComponent(targetId)}${params}`)
        this.files = data.files
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      } finally {
        this.loading = false
      }
    },
    async fetchTrash() {
      try {
        const targetId = this.viewSessionId || this.sessionId
        const params = this.viewAllowArchived ? '?allow_archived=true' : ''
        const data = await fetchJson<{ session_id: string; items: ArtifactTrashEntry[] }>(
          `/api/artifacts/trash?session_id=${encodeURIComponent(targetId)}${params}`
        )
        this.trash = data.items
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      }
    },
    async fetchAudit(limit = 20) {
      try {
        const targetId = this.viewSessionId || this.sessionId
        const params = new URLSearchParams()
        params.set('session_id', targetId)
        if (this.viewAllowArchived) params.set('allow_archived', 'true')
        params.set('limit', String(limit))
        const data = await fetchJson<{ session_id: string; items: ArtifactAuditEntry[] }>(
          `/api/artifacts/audit?${params.toString()}`
        )
        this.audit = data.items
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      }
    },
    async deleteArtifact(path: string, reason?: string) {
      const payload = {
        session_id: this.viewSessionId || this.sessionId,
        path,
        reason: reason || null,
        actor: 'user',
        allow_archived: this.viewAllowArchived
      }
      const data = await fetchJson<{
        trash_id: string
        path: string
        freed_bytes: number
        restore_until: string
        retention_days: number
      }>('/api/artifacts/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      await Promise.all([this.fetchArtifacts(), this.fetchTrash(), this.fetchAudit(20)])
      return data
    },
    async restoreArtifact(trashId: string) {
      const payload = {
        session_id: this.viewSessionId || this.sessionId,
        trash_id: trashId,
        actor: 'user',
        allow_archived: this.viewAllowArchived
      }
      const data = await fetchJson<{ path: string; size_bytes: number; restored_at: string }>(
        '/api/artifacts/restore',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }
      )
      await Promise.all([this.fetchArtifacts(), this.fetchTrash(), this.fetchAudit(20)])
      return data
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
          const data = JSON.parse((evt as MessageEvent).data) as {
            path?: string
            op?: string
            freed_bytes?: number
            restore_until?: string
            count?: number
          }
          this.unreadCount += 1
          let msg = data.path ? `Nuevo artefacto: ${data.path}` : 'Nuevo artefacto'
          if (data.op === 'delete') {
            msg = data.path
              ? `Eliminado: ${data.path} · ${this.formatBytes(data.freed_bytes || 0)}`
              : 'Artefacto eliminado'
          } else if (data.op === 'restore') {
            msg = data.path ? `Restaurado: ${data.path}` : 'Artefacto restaurado'
          } else if (data.op === 'cleanup') {
            msg = `Limpieza automática: ${data.count || 0} eliminados`
          }
          const toast = { id: `${Date.now()}_${Math.random()}`, message: msg }
          this.toasts.push(toast)
          bus.emit('toast:push', toast)
          bus.emit('artifact:event', data as any)
          window.setTimeout(() => this.popToast(toast.id), 4500)
        } catch {
          this.unreadCount += 1
        } finally {
          if (this.viewSessionId === this.sessionId) {
            debouncedRefresh()
          }
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
    },
    formatBytes(n: number) {
      if (n < 1024) return `${n} B`
      const kb = n / 1024
      if (kb < 1024) return `${kb.toFixed(1)} KB`
      const mb = kb / 1024
      return `${mb.toFixed(1)} MB`
    }
  }
})
