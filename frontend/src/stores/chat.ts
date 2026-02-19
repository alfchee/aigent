import { defineStore } from 'pinia'

import { ApiError, fetchJson } from '../lib/api'
import { useSessionsStore } from './sessions'

export type ChatMessage = {
  id?: number
  role: 'user' | 'assistant'
  content: string
  created_at?: string | null
}

type ChatResponse = {
  response: string
}

type SessionMessagesResponse = {
  session_id: string
  items: Array<{
    id: number
    role: 'user' | 'assistant'
    content: string
    created_at: string | null
    corrupted?: boolean
  }>
  has_more: boolean
  next_before_id: number | null
  limit: number
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [
      { role: 'assistant', content: '¡Hola! Soy Navibot. ¿En qué puedo ayudarte hoy?' },
    ] as ChatMessage[],
    isLoading: false as boolean,
    error: null as string | null,
    isHistoryLoading: false as boolean,
    historyError: null as string | null,
    historyHasMore: false as boolean,
    historyNextBeforeId: null as number | null,
  }),
  actions: {
    async loadSessionHistory(sessionId: string) {
      this.isHistoryLoading = true
      this.historyError = null
      try {
        const data = await fetchJson<SessionMessagesResponse>(
          `/api/sessions/${encodeURIComponent(sessionId || 'default')}/messages?limit=50`,
        )
        const items = (data.items || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
        }))
        this.messages =
          items.length > 0
            ? items
            : [{ role: 'assistant', content: '¡Hola! Soy Navibot. ¿En qué puedo ayudarte hoy?' }]
        this.historyHasMore = Boolean(data.has_more)
        this.historyNextBeforeId = data.has_more ? data.next_before_id : null
      } catch (e) {
        this.historyError = e instanceof Error ? e.message : String(e)
      } finally {
        this.isHistoryLoading = false
      }
    },
    async loadMoreHistory(sessionId: string) {
      if (this.isHistoryLoading || !this.historyHasMore || !this.historyNextBeforeId) return
      this.isHistoryLoading = true
      this.historyError = null
      try {
        const data = await fetchJson<SessionMessagesResponse>(
          `/api/sessions/${encodeURIComponent(sessionId || 'default')}/messages?limit=50&before_id=${this.historyNextBeforeId}`,
        )
        const items = (data.items || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
        }))
        if (items.length > 0) {
          this.messages = [...items, ...this.messages]
        }
        this.historyHasMore = Boolean(data.has_more)
        this.historyNextBeforeId = data.has_more ? data.next_before_id : null
      } catch (e) {
        this.historyError = e instanceof Error ? e.message : String(e)
      } finally {
        this.isHistoryLoading = false
      }
    },
    async sendMessage(message: string, sessionId: string, modelName?: string) {
      const trimmed = message.trim()
      if (!trimmed || this.isLoading) return
      this.messages.push({ role: 'user', content: trimmed })
      this.isLoading = true
      this.error = null
      try {
        const model_name = (modelName || '').trim()
        const memory_user_id = (localStorage.getItem('navibot_memory_user_id') || '').trim()
        const data = await fetchJson<ChatResponse>('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: trimmed,
            session_id: sessionId,
            model_name: model_name || undefined,
            memory_user_id: memory_user_id || undefined,
          }),
        })
        this.messages.push({
          role: 'assistant',
          content: data.response || 'No recibí respuesta del agente.',
        })
        try {
          const userCount = this.messages.filter((m) => m.role === 'user').length
          const assistantCount = this.messages.filter((m) => m.role === 'assistant').length
          if (userCount === 1 && assistantCount === 2) {
            const sessions = useSessionsStore()
            await sessions.autotitle(sessionId)
          }
        } catch (error) {
          void error
        }
      } catch (e) {
        let msg = e instanceof Error ? e.message : String(e)
        if (e instanceof ApiError) {
          const body = e.body as any
          if (typeof body === 'string' && body.trim()) msg = body
          else if (body && typeof body.detail === 'string') msg = body.detail
          else msg = `HTTP ${e.status}`
        }
        this.error = msg
        this.messages.push({ role: 'assistant', content: `Lo siento, hubo un error: ${msg}` })
      } finally {
        this.isLoading = false
      }
    },
  },
})
