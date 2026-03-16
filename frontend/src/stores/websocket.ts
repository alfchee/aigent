import { defineStore } from 'pinia'
import type { InboundWsEnvelope, OutboundWsEnvelope } from '@/types/chat'
import { WebSocketClient, type WsStatus } from '@/services/websocketClient'
import { logEvent } from '@/services/logger'
import { createRateLimiter } from '@/services/rateLimit'
import { useUserConfigStore } from '@/stores/userConfig'
import { useMessagesStore } from '@/stores/messages'

type WsState = {
  status: WsStatus
  lastError: string | null
  latencyMs: number | null
  reconnectCount: number
  lastConnectedAt: number | null
  outbox: OutboundWsEnvelope[]
}

function computeWsUrl(sessionId: string) {
  const explicit = import.meta.env.VITE_WS_URL as string | undefined
  if (explicit && explicit.startsWith('ws')) {
    if (explicit.includes('{sessionId}'))
      return explicit.replace('{sessionId}', sessionId)
    return `${explicit.replace(/\/+$/, '')}/${sessionId}`
  }

  const basePath = (import.meta.env.VITE_WS_BASE_PATH as string | undefined) ?? '/ws'
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = location.host
  const norm = basePath.startsWith('/') ? basePath : `/${basePath}`
  return `${proto}//${host}${norm}/${sessionId}`
}

const limiter = createRateLimiter({ windowMs: 10_000, max: 12 })

export const useWebSocketStore = defineStore('websocket', {
  state: (): WsState => ({
    status: 'idle',
    lastError: null,
    latencyMs: null,
    reconnectCount: 0,
    lastConnectedAt: null,
    outbox: [],
  }),
  actions: {
    connect() {
      const user = useUserConfigStore()
      const url = computeWsUrl(user.sessionId)
      const messages = useMessagesStore()

      const client = new WebSocketClient(
        {
          url,
          sessionId: user.sessionId,
          heartbeatIntervalMs: 15_000,
          reconnect: {
            enabled: true,
            baseDelayMs: 600,
            maxDelayMs: 15_000,
            maxRetries: 50,
          },
        },
        {
          onStatus: (s) => {
            if (this.status !== s && s === 'reconnecting') this.reconnectCount += 1
            this.status = s
            if (s === 'open') {
              this.lastConnectedAt = Date.now()
              this.lastError = null
              this.flushOutbox()
            }
          },
          onMessage: (m) => {
            this.handleInbound(m)
            if (m.type === 'ack') {
              const convId = messages.activeConversationId
              if (convId) {
                const list = messages.messagesByConversationId[convId] ?? []
                const lastSending = [...list]
                  .reverse()
                  .find((x) => x.role === 'user' && x.status === 'sending')
                if (lastSending)
                  messages.updateMessageStatus(convId, lastSending.id, 'delivered')
              }
              const active = messages.activeConversationId
              if (active) messages.setAssistantTyping(active, false)
            }
            if (
              m.type === 'assistant_message' &&
              typeof (m as any).conversationId === 'string' &&
              typeof (m as any).messageId === 'string' &&
              typeof (m as any).text === 'string' &&
              typeof (m as any).createdAt === 'number'
            ) {
              const conversationId = (m as any).conversationId as string
              messages
                .addMessage({
                  conversationId,
                  role: 'assistant',
                  text: (m as any).text as string,
                  status: 'delivered',
                  id: (m as any).messageId as string,
                  createdAt: (m as any).createdAt as number,
                })
                .catch(() => {})
              messages.setAssistantTyping(conversationId, false)
              if (messages.activeConversationId === conversationId)
                messages.markAllRead(conversationId)
            }
          },
          onError: (e) => {
            this.lastError = e.message
          },
          onLatency: (lat) => {
            this.latencyMs = lat
          },
        },
      )

      ;(this as any)._client?.disconnect?.()
      ;(this as any)._client = client

      client.connect()
    },
    disconnect() {
      ;(this as any)._client?.disconnect?.()
      ;(this as any)._client = null
      this.status = 'closed'
    },
    handleInbound(msg: InboundWsEnvelope) {
      logEvent({ level: 'debug', name: 'ws_in', data: { type: msg.type } })
    },
    enqueue(out: OutboundWsEnvelope) {
      this.outbox.push(out)
    },
    flushOutbox() {
      const client: WebSocketClient | null = (this as any)._client ?? null
      if (!client || client.getStatus() !== 'open') return
      const pending = this.outbox
      this.outbox = []
      for (const msg of pending) {
        const res = client.sendJson(msg)
        if (!res.ok) {
          this.outbox.unshift(msg)
          this.lastError = res.error
          break
        }
      }
    },
    send(out: OutboundWsEnvelope) {
      if (!limiter.canSend()) {
        return { ok: false as const, error: 'Demasiados mensajes: espera unos segundos.' }
      }

      limiter.recordSend()
      const client: WebSocketClient | null = (this as any)._client ?? null
      if (!client || client.getStatus() !== 'open') {
        this.enqueue(out)
        return { ok: true as const, queued: true as const }
      }

      const res = client.sendJson(out)
      if (!res.ok) {
        this.enqueue(out)
        return { ok: true as const, queued: true as const }
      }
      return { ok: true as const, queued: false as const }
    },
  },
})
