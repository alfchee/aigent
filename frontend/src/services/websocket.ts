import { ref } from 'vue'

export type WebSocketEvent =
  | 'connection.ack'
  | 'agent.token'
  | 'agent.tool_start'
  | 'agent.tool_end'
  | 'agent.response'
  | 'error'
  | 'pong'

export interface WebSocketMessage {
  type: string
  data?: any
  content?: any
  id?: string
  client_id?: string
  status?: string
  code?: string
  message?: string
}

type EventHandler = (data: any) => void

export class WebSocketService {
  private static instance: WebSocketService
  private socket: WebSocket | null = null
  private url: string = ''
  private clientId: string = ''
  private reconnectAttempts: number = 0
  private maxReconnectAttempts: number = 10
  private reconnectDelay: number = 1000
  private isConnecting: boolean = false
  private shouldReconnect: boolean = true
  private eventHandlers: Map<string, EventHandler[]> = new Map()
  private pingInterval: number | null = null

  // Observable state
  public isConnected = ref(false)

  private constructor() {}

  public static getInstance(): WebSocketService {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService()
    }
    return WebSocketService.instance
  }

  public connect(url: string, clientId: string) {
    const targetChanged = this.url !== url || this.clientId !== clientId

    if (this.isConnecting) {
      if (targetChanged) {
        this.disconnect(true)
      } else {
        console.log('WebSocket already connecting')
        return
      }
    }

    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)
    ) {
      if (targetChanged) {
        this.disconnect(true)
      } else {
        console.log('WebSocket already connected or connecting')
        return
      }
    }

    this.url = url
    this.clientId = clientId
    this.isConnecting = true
    this.shouldReconnect = true
    this.reconnectAttempts = 0

    this._connect()
  }

  private _connect() {
    console.log(`Connecting to WebSocket: ${this.url}`)

    if (!window.WebSocket) {
      console.error('Browser does not support WebSocket')
      this.isConnecting = false
      this.handleMessage({
        type: 'connection.error',
        data: { message: 'Browser does not support WebSocket' },
      })
      return
    }

    try {
      this.socket = new WebSocket(this.url)

      this.socket.onopen = () => {
        console.log('WebSocket connected')
        this.isConnected.value = true
        this.isConnecting = false
        this.shouldReconnect = true
        this.reconnectAttempts = 0
        this.startPing()

        this.handleMessage({ type: 'connection.open', data: { clientId: this.clientId } })
      }

      this.socket.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          if (message.type === 'pong') {
            return
          }
          this.handleMessage(message)
        } catch (e) {
          console.error('Error parsing WebSocket message:', e)
        }
      }

      this.socket.onclose = (event) => {
        console.log('WebSocket disconnected', event.code, event.reason)
        this.isConnected.value = false
        this.isConnecting = false
        this.stopPing()

        this.handleMessage({
          type: 'connection.close',
          data: { code: event.code, reason: event.reason },
        })

        if (this.shouldReconnect && !event.wasClean) {
          this.handleReconnect()
        }
      }

      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error)
        this.handleMessage({ type: 'connection.error', data: error })
      }
    } catch (e) {
      console.error('WebSocket connection failed:', e)
      this.isConnecting = false
      this.handleReconnect()
    }
  }

  private handleReconnect() {
    if (!this.shouldReconnect) {
      this.isConnecting = false
      return
    }

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts)
      console.log(`Reconnecting in ${delay}ms... (Attempt ${this.reconnectAttempts + 1})`)

      this.isConnecting = true

      // Emit reconnecting event with attempt info
      this.handleMessage({
        type: 'connection.reconnecting',
        data: {
          attempt: this.reconnectAttempts + 1,
          maxAttempts: this.maxReconnectAttempts,
          delay,
        },
      })

      setTimeout(() => {
        this.reconnectAttempts++
        this._connect()
      }, delay)
    } else {
      console.error('Max reconnection attempts reached')
      this.isConnecting = false
      this.handleMessage({ type: 'connection.max_reconnect_attempts' })
    }
  }

  public disconnect(manual: boolean = true) {
    this.shouldReconnect = !manual
    this.isConnecting = false
    this.reconnectAttempts = 0
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
    this.isConnected.value = false
    this.stopPing()
  }

  public send(type: string, payload: any = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected')
      return
    }

    const message = {
      type,
      ...payload,
    }
    this.socket.send(JSON.stringify(message))
  }

  public on(event: string, handler: EventHandler) {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, [])
    }
    this.eventHandlers.get(event)?.push(handler)
  }

  public off(event: string, handler: EventHandler) {
    if (!this.eventHandlers.has(event)) return

    const handlers = this.eventHandlers.get(event)
    if (handlers) {
      const index = handlers.indexOf(handler)
      if (index !== -1) {
        handlers.splice(index, 1)
      }
    }
  }

  private handleMessage(message: WebSocketMessage) {
    const type = message.type
    const handlers = this.eventHandlers.get(type)

    if (handlers) {
      handlers.forEach((handler) => handler(message.data || message))
    }

    // Also trigger generic message handler if needed
    // console.log('Received:', message)
  }

  private startPing() {
    this.stopPing()
    this.pingInterval = window.setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.send('ping')
      }
    }, 30000) // Ping every 30s
  }

  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }
}
