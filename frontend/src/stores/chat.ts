import { defineStore } from 'pinia'

import { ApiError, NetworkError, TimeoutError, fetchJson } from '../lib/api'
import { useSessionsStore } from './sessions'
import { useModelSettingsStore } from './modelSettings'
import { WebSocketService } from '../services/websocket'

let wsService: WebSocketService | null = null

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
    wsConnected: false as boolean,
    connectedSessionId: null as string | null,
  }),
  actions: {
    initWebSocket(sessionId: string) {
      if (!wsService) {
        wsService = WebSocketService.getInstance()

        // Subscribe to events
        wsService.on('connection.open', (data: { clientId?: string }) => {
          this.wsConnected = true
          this.connectedSessionId = data?.clientId || null
          this.error = null // Clear connection errors
        })

        wsService.on('connection.close', () => {
          this.wsConnected = false
          this.connectedSessionId = null
        })

        wsService.on('connection.error', (err: any) => {
          console.error('WS Error:', err)
          // Don't show error to user immediately unless it persists, handled by reconnect
        })

        wsService.on('agent.token', (data: any) => {
          this.handleAgentToken(data)
        })

        wsService.on('agent.tool_start', (data: any) => {
          this.handleToolStart(data)
        })

        wsService.on('agent.tool_end', (data: any) => {
          this.handleToolEnd(data)
        })

        wsService.on('agent.response', (data: any) => {
          this.handleAgentResponse(data)
        })

        wsService.on('error', (data: any) => {
          this.handleAgentError(data)
        })

        // Handle done event
        wsService.on('done', (data: any) => {
          this.handleStreamDone(data)
        })

        // Handle connection status changes
        wsService.on(
          'connection.reconnecting',
          (data: { attempt: number; maxAttempts: number; delay: number }) => {
            this.currentThought = `Reconectando (${data.attempt}/${data.maxAttempts})...`
            this.error = null
          },
        )

        wsService.on('connection.max_reconnect_attempts', () => {
          this.wsConnected = false
          this.error = 'Conexión perdida. Por favor, recarga la página para reconnectar.'
        })
      }

      // Connect
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      let wsUrl = `${protocol}//${host}/api/ws/chat/${sessionId}`

      // If using VITE_API_URL, we should use that
      const apiUrl = (import.meta as any).env.VITE_API_URL
      if (apiUrl) {
        const url = new URL(apiUrl)
        const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
        wsUrl = `${wsProtocol}//${url.host}/api/ws/chat/${sessionId}`
      }

      if (this.connectedSessionId && this.connectedSessionId !== sessionId) {
        this.wsConnected = false
        wsService.disconnect(true)
      }

      wsService.connect(wsUrl, sessionId)
    },

    handleAgentToken(data: { content: string }) {
      if (!this.isStreaming) return

      this.currentThought = 'Generando respuesta...'

      // Append to the last message if it's assistant, or create new
      const lastMsg = this.messages[this.messages.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        lastMsg.content += data.content
      } else {
        this.messages.push({ role: 'assistant', content: data.content })
      }
    },

    handleToolStart(data: { tool: string; input: string }) {
      this.currentThought = `Ejecutando herramienta: ${data.tool}`
      this.logs.push({
        id: Date.now().toString(),
        title: `Using tool: ${data.tool}`,
        type: 'tool',
        timestamp: Date.now(),
        message: `Input: ${data.input}`,
        expanded: false,
      })
    },

    handleToolEnd(data: { tool: string; output: string }) {
      // Find the last log for this tool? Or just add a completion log?
      // For now, add a completion log or update existing?
      // Let's add a new log for completion
      this.logs.push({
        id: Date.now().toString(),
        title: `Tool finished: ${data.tool}`,
        type: 'success',
        timestamp: Date.now(),
        message: `Output: ${data.output}`,
        expanded: false,
      })
    },

    handleAgentResponse(data: { content: string; done: boolean }) {
      if (data.done) {
        this.isLoading = false
        this.isStreaming = false
        this.currentThought = ''

        // Ensure content is up to date (though token stream should have handled it)
        // If content is provided and different/full, maybe replace?
        // Usually token stream builds it up.
        // But if we missed tokens, this ensures consistency.
        // For now, assume tokens were sufficient or data.content is the full response.
        const lastMsg = this.messages[this.messages.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          // Verify if we need to update
          if (data.content && data.content.length > lastMsg.content.length) {
            lastMsg.content = data.content
          }
        }
      }
    },

    handleAgentError(data: { message: string }) {
      this.error = data.message
      this.isLoading = false
      this.isStreaming = false
      this.currentThought = ''
      this.messages.push({ role: 'assistant', content: `Error: ${data.message}` })
    },

    handleStreamDone(data: { id?: string; cancelled?: boolean; error?: boolean }) {
      // Stream is complete
      // Handle cancelled or error states
      if (data.cancelled) {
        // The message was cancelled, the UI already handles this
      } else if (data.error) {
        // There was an error, already handled by handleAgentError
      }
      this.isLoading = false
      this.isStreaming = false
      this.currentThought = ''
    },

    stopGeneration() {
      // Send stop signal via WS
      if (wsService && this.wsConnected) {
        wsService.send('chat.stop')
      }
      this.isLoading = false
      this.isStreaming = false
    },
    async loadSessionHistory(sessionId: string) {
      this.isHistoryLoading = true
      this.historyError = null

      // Initialize WebSocket for this session
      this.initWebSocket(sessionId)

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
      this.isStreaming = true // Enable streaming mode
      this.error = null
      this.logs = [] // Clear previous logs

      // Create a placeholder message for assistant
      this.messages.push({ role: 'assistant', content: '' })

      // Try WebSocket first
      if (wsService && this.wsConnected && this.connectedSessionId === currentSessionId) {
        try {
          wsService.send('chat.message', {
            content: trimmed,
            id: crypto.randomUUID(), // requires secure context or polyfill, fall back to Date.now() if needed
            timestamp: Date.now(),
          })
          // Wait for events...
          return
        } catch (e) {
          console.error('WS Send failed, falling back to HTTP', e)
          // Fallback proceeds below
        }
      } else {
        // Try to connect if not connected
        this.initWebSocket(currentSessionId)
        // Check again after short delay? No, just use HTTP fallback for this message
        console.warn('WebSocket not connected, using HTTP fallback')
      }

      // HTTP Fallback
      // Remove the empty assistant message we added for streaming
      this.messages.pop()
      this.isStreaming = false // Disable streaming flag for HTTP

      try {
        const model_name = (modelName || '').trim()
        const memory_user_id = (localStorage.getItem('navibot_memory_user_id') || '').trim()

        // Get execution timeout from settings or default to 5 minutes
        const settings = useModelSettingsStore()
        const timeoutSeconds = settings.limitsConfig.execution_timeout_seconds || 300
        const timeoutMs = timeoutSeconds * 1000

        const data = await fetchJson<ChatResponse>('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          timeout: timeoutMs,
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
          msg = `Request timed out after ${e.timeout / 1000}s. Please check your connection or increase the timeout in settings.`
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
