import { defineStore } from 'pinia'

import { ApiError, NetworkError, TimeoutError, fetchJson } from '../lib/api'
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

export type ChatLog = {
  id: string
  title: string
  type: 'thinking' | 'tool' | 'success' | 'error' | 'info'
  timestamp: number
  message?: string
  details?: any
  expanded?: boolean
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [
      { role: 'assistant', content: 'Hello! I am Navibot. How can I help you today?' },
    ] as ChatMessage[],
    isLoading: false as boolean,
    isStreaming: false as boolean,
    currentThought: '' as string,
    logs: [] as ChatLog[],
    error: null as string | null,
    isHistoryLoading: false as boolean,
    historyError: null as string | null,
    historyHasMore: false as boolean,
    historyNextBeforeId: null as number | null,
  }),
  actions: {
    stopGeneration() {
      // TODO: Implement abort controller for fetch
      this.isLoading = false
      this.isStreaming = false
    },
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
            : [{ role: 'assistant', content: 'Hello! I am Navibot. How can I help you today?' }]
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
    async sendMessage(message: string, sessionId?: string, modelName?: string) {
      const trimmed = message.trim()
      if (!trimmed || this.isLoading) return

      const currentSessionId = sessionId || 'default'

      this.messages.push({ role: 'user', content: trimmed })
      this.isLoading = true
      this.error = null
      try {
        const model_name = (modelName || '').trim()
        const memory_user_id = (localStorage.getItem('navibot_memory_user_id') || '').trim()
        const data = await fetchJson<ChatResponse>('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          timeout: 120000, // 2 minutes timeout for agent operations
          body: JSON.stringify({
            message: trimmed,
            session_id: currentSessionId,
            model_name: model_name || undefined,
            memory_user_id: memory_user_id || undefined,
          }),
        })
        this.messages.push({
          role: 'assistant',
          content: data.response || 'No response from agent.',
        })
        try {
          const userCount = this.messages.filter((m) => m.role === 'user').length
          const assistantCount = this.messages.filter((m) => m.role === 'assistant').length
          if (userCount === 1 && assistantCount === 2) {
            const sessions = useSessionsStore()
            await sessions.autotitle(currentSessionId)
          }
        } catch (error) {
          void error
        }
      } catch (e: any) {
        let msg = 'Unknown error'

        if (e instanceof TimeoutError) {
          msg = 'The request took too long. Please check your connection and try again.'
        } else if (e instanceof NetworkError) {
          msg = 'Could not connect to the server. Check that the backend is running and accessible.'
          if (e.originalError instanceof Error) {
            msg += ` (${e.originalError.message})`
          }
        } else if (e instanceof ApiError) {
          const body = e.body as any
          if (typeof body === 'string' && body.trim()) msg = body
          else if (body && typeof body.detail === 'string') msg = body.detail
          else msg = `Server error (HTTP ${e.status})`
        } else if (e instanceof Error) {
          msg = e.message
        } else if (typeof e === 'string') {
          msg = e
        }

        this.error = msg
        this.messages.push({ role: 'assistant', content: `Sorry, there was an error: ${msg}` })
      } finally {
        this.isLoading = false
      }
    },
  },
})
