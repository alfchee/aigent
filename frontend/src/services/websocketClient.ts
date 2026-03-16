import type { InboundWsEnvelope, OutboundWsEnvelope } from '@/types/chat'
import { logEvent } from '@/services/logger'

export type WsStatus =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed'
  | 'error'

export type WebSocketClientOptions = {
  url: string
  sessionId: string
  heartbeatIntervalMs: number
  reconnect: {
    enabled: boolean
    baseDelayMs: number
    maxDelayMs: number
    maxRetries: number
  }
}

export type WebSocketClientEvents = {
  onStatus?: (s: WsStatus) => void
  onMessage?: (m: InboundWsEnvelope) => void
  onError?: (err: { name: string; message: string }) => void
  onLatency?: (latencyMs: number | null) => void
}

export class WebSocketClient {
  private ws: WebSocket | null = null
  private status: WsStatus = 'idle'
  private retry = 0
  private heartbeatTimer: number | null = null
  private lastPingAt: number | null = null
  private lastLatency: number | null = null
  private closedByUser = false

  constructor(
    private opts: WebSocketClientOptions,
    private events: WebSocketClientEvents = {},
  ) {}

  getStatus() {
    return this.status
  }

  getLatencyMs() {
    return this.lastLatency
  }

  connect() {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return
    }
    this.closedByUser = false
    this.setStatus(this.retry > 0 ? 'reconnecting' : 'connecting')

    try {
      this.ws = new WebSocket(this.opts.url)
    } catch (e) {
      this.failWithError('ws_ctor_error', e instanceof Error ? e.message : String(e))
      this.scheduleReconnect()
      return
    }

    this.ws.addEventListener('open', () => {
      this.retry = 0
      this.setStatus('open')
      this.startHeartbeat()
    })

    this.ws.addEventListener('message', (evt) => {
      const raw = typeof evt.data === 'string' ? evt.data : ''
      const parsed = this.parseInbound(raw)
      if (!parsed) return

      if (parsed.type === 'pong' && typeof parsed.ts === 'number' && this.lastPingAt) {
        const latency = Math.max(0, Date.now() - this.lastPingAt)
        this.lastLatency = latency
        this.events.onLatency?.(latency)
      }

      this.events.onMessage?.(parsed)
    })

    this.ws.addEventListener('close', (evt) => {
      this.stopHeartbeat()
      if (this.closedByUser) {
        this.setStatus('closed')
        return
      }

      logEvent({
        level: 'warn',
        name: 'ws_close',
        data: { code: evt.code, reason: evt.reason, wasClean: evt.wasClean },
      })

      this.setStatus('closed')
      this.scheduleReconnect()
    })

    this.ws.addEventListener('error', () => {
      this.stopHeartbeat()
      this.failWithError('ws_error', 'Error de red en WebSocket')
      try {
        this.ws?.close()
      } catch {
        // ignore
      }
    })
  }

  disconnect() {
    this.closedByUser = true
    this.stopHeartbeat()
    try {
      this.ws?.close()
    } finally {
      this.ws = null
      this.setStatus('closed')
    }
  }

  sendJson(msg: OutboundWsEnvelope) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return { ok: false as const, error: 'WebSocket no conectado' }
    }

    try {
      this.ws.send(JSON.stringify(msg))
      return { ok: true as const }
    } catch (e) {
      return { ok: false as const, error: e instanceof Error ? e.message : String(e) }
    }
  }

  private setStatus(s: WsStatus) {
    this.status = s
    this.events.onStatus?.(s)
  }

  private failWithError(name: string, message: string) {
    this.setStatus('error')
    this.events.onError?.({ name, message })
    logEvent({ level: 'error', name, data: { message } })
  }

  private scheduleReconnect() {
    const r = this.opts.reconnect
    if (!r.enabled) return
    if (this.retry >= r.maxRetries) return

    this.retry += 1
    const base = Math.min(r.maxDelayMs, r.baseDelayMs * Math.pow(2, this.retry - 1))
    const jitter = base * (0.2 * Math.random())
    const delay = Math.round(base + jitter)

    this.setStatus('reconnecting')
    window.setTimeout(() => {
      if (this.closedByUser) return
      this.connect()
    }, delay)
  }

  private startHeartbeat() {
    this.stopHeartbeat()
    const interval = Math.max(5_000, this.opts.heartbeatIntervalMs)
    this.heartbeatTimer = window.setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
      this.lastPingAt = Date.now()
      const sent = this.sendJson({
        type: 'ping',
        sessionId: this.opts.sessionId,
        ts: this.lastPingAt,
      })
      if (!sent.ok) {
        this.failWithError('ws_ping_failed', sent.error)
      }
    }, interval)
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      window.clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    this.lastPingAt = null
    this.lastLatency = null
    this.events.onLatency?.(null)
  }

  private parseInbound(raw: string): InboundWsEnvelope | null {
    if (!raw) return null
    try {
      const data = JSON.parse(raw) as unknown
      if (!data || typeof data !== 'object') return null
      const t = (data as any).type
      if (typeof t !== 'string') return null
      return data as InboundWsEnvelope
    } catch {
      return null
    }
  }
}
