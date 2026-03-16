import type { InboundWsEnvelope } from '@/types/chat'

export function setupMockWsIfEnabled() {
  const enabled = (import.meta.env.VITE_ENABLE_MOCK_WS as any) === '1'
  if (!enabled) return

  const RealWs = window.WebSocket
  const nextMessageId = () => {
    const randomUUID = globalThis.crypto?.randomUUID?.bind(globalThis.crypto)
    if (randomUUID) return randomUUID()
    return `mock-${Date.now()}-${Math.random().toString(16).slice(2)}`
  }

  class FakeWebSocket {
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3

    CONNECTING = 0
    OPEN = 1
    CLOSING = 2
    CLOSED = 3

    url: string
    readyState = FakeWebSocket.CONNECTING
    onopen: ((ev: Event) => void) | null = null
    onmessage: ((ev: MessageEvent) => void) | null = null
    onclose: ((ev: CloseEvent) => void) | null = null
    onerror: ((ev: Event) => void) | null = null

    private listeners: Record<string, any[]> = {}

    constructor(url: string) {
      this.url = url
      window.setTimeout(() => {
        this.readyState = FakeWebSocket.OPEN
        this.onopen?.(new Event('open'))
        for (const cb of this.listeners['open'] ?? []) cb(new Event('open'))
      }, 80)
    }

    addEventListener(type: string, cb: any) {
      this.listeners[type] = this.listeners[type] ?? []
      this.listeners[type].push(cb)
    }

    send(data: string) {
      const ack: InboundWsEnvelope = { type: 'ack', content: 'ok', ts: Date.now() }
      window.setTimeout(() => {
        this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(ack) }))
        for (const cb of this.listeners['message'] ?? []) {
          cb(new MessageEvent('message', { data: JSON.stringify(ack) }))
        }
      }, 60)

      try {
        const parsed = JSON.parse(data) as any
        if (parsed?.type === 'user_message' && typeof parsed.text === 'string') {
          const reply: InboundWsEnvelope = {
            type: 'assistant_message',
            conversationId: parsed.conversationId,
            messageId: nextMessageId(),
            text: `Echo: ${parsed.text}`,
            createdAt: Date.now(),
          }
          window.setTimeout(() => {
            this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(reply) }))
            for (const cb of this.listeners['message'] ?? []) {
              cb(new MessageEvent('message', { data: JSON.stringify(reply) }))
            }
          }, 450)
        }
        if (parsed?.type === 'ping') {
          const pong: InboundWsEnvelope = { type: 'pong', ts: Date.now() }
          window.setTimeout(() => {
            this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(pong) }))
            for (const cb of this.listeners['message'] ?? []) {
              cb(new MessageEvent('message', { data: JSON.stringify(pong) }))
            }
          }, 40)
        }
      } catch {
        // ignore
      }
    }

    close() {
      this.readyState = FakeWebSocket.CLOSED
      const ev = new CloseEvent('close', { code: 1000, reason: 'mock close' })
      this.onclose?.(ev)
      for (const cb of this.listeners['close'] ?? []) cb(ev)
    }
  }

  ;(window as any).WebSocket = FakeWebSocket as unknown as typeof RealWs
}
