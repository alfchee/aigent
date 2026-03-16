export type MessageRole = 'user' | 'assistant' | 'system'

export type MessageStatus = 'sending' | 'sent' | 'delivered' | 'read' | 'error'

export type Conversation = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  tags: string[]
  agentId?: string
  archived?: boolean
}

export type ChatMessage = {
  id: string
  conversationId: string
  role: MessageRole
  text: string
  createdAt: number
  status: MessageStatus
  meta?: Record<string, unknown>
}

export type OutboundWsEnvelope =
  | {
      type: 'user_message'
      sessionId: string
      conversationId: string
      messageId: string
      text: string
      createdAt: number
      agentId?: string
      e2ee?: boolean
    }
  | {
      type: 'ping'
      sessionId: string
      ts: number
    }

export type InboundWsEnvelope =
  | {
      type: 'ack'
      content?: string
      ts?: number
    }
  | {
      type: 'assistant_message'
      conversationId: string
      messageId: string
      text: string
      createdAt: number
    }
  | {
      type: 'pong'
      ts: number
    }
  | {
      type: string
      [k: string]: unknown
    }
