import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useMessagesStore } from '@/stores/messages'
import { useWebSocketStore } from '@/stores/websocket'

describe('websocket store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('registra eventos status y activa typing', async () => {
    const messages = useMessagesStore()
    const conversation = await messages.createConversation()
    const ws = useWebSocketStore()
    ws.lastOutboundConversationId = conversation.id

    ws.handleInbound({
      type: 'status',
      action: 'Analyzing',
      details: 'Processing user request',
    })

    const events = ws.executionEventsByConversationId[conversation.id] ?? []
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('status')
    expect(events[0].label).toContain('Analyzing')
    expect(messages.assistantTypingByConversationId[conversation.id]).toBe(true)
  })

  it('registra tool_call y error en el timeline de ejecución', async () => {
    const messages = useMessagesStore()
    const conversation = await messages.createConversation()
    const ws = useWebSocketStore()
    ws.lastOutboundConversationId = conversation.id

    ws.handleInbound({
      type: 'tool_call',
      tool_name: 'python_sandbox',
      details: 'Executing validated code',
    })
    ws.handleInbound({
      type: 'error',
      content: 'Timeout',
    })

    const events = ws.executionEventsByConversationId[conversation.id] ?? []
    expect(events).toHaveLength(2)
    expect(events[0].type).toBe('tool_call')
    expect(events[1].type).toBe('error')
    expect(messages.assistantTypingByConversationId[conversation.id]).toBe(false)
  })
})
