import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useMessagesStore } from './messages'
import * as chatApi from '@/services/chatApi'

describe('messages store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('crea conversación y asigna id activo', async () => {
    const store = useMessagesStore()
    const c = await store.createConversation()
    expect(store.activeConversationId).toBe(c.id)
    expect(store.conversations[0].id).toBe(c.id)
  })

  it('usa el primer mensaje del usuario como título inicial', async () => {
    const store = useMessagesStore()
    const c = await store.createConversation()
    await store.addMessage({
      conversationId: c.id,
      role: 'user',
      text: 'Hola mundo',
      status: 'sent',
    })
    expect(store.conversations[0].title.toLowerCase()).toContain('hola')
  })

  it('permite actualizar agente y carpeta de conversación', async () => {
    const store = useMessagesStore()
    const c = await store.createConversation()
    await store.setConversationAgent(c.id, 'planner')
    await store.setConversationFolder(c.id, 'Clientes')
    const updated = store.conversations.find((x) => x.id === c.id)
    expect(updated?.agentId).toBe('planner')
    expect(updated?.folder).toBe('Clientes')
  })

  it('reconcilia mensajes repetidos por id con estado más avanzado', async () => {
    const store = useMessagesStore()
    const c = await store.createConversation()
    store.mergeMessages(c.id, [
      {
        id: 'm1',
        conversationId: c.id,
        role: 'user',
        text: 'Hola',
        createdAt: 1000,
        status: 'sent',
      },
    ])
    const merged = store.mergeMessages(c.id, [
      {
        id: 'm1',
        conversationId: c.id,
        role: 'user',
        text: 'Hola',
        createdAt: 1000,
        status: 'delivered',
      },
    ])
    expect(merged).toHaveLength(1)
    expect(merged[0].status).toBe('delivered')
  })

  it('usa paginación remota en loadMore cuando feature flag está activa', async () => {
    const store = useMessagesStore()
    const c = await store.createConversation()
    store.messagesByConversationId[c.id] = [
      {
        id: 'm-new',
        conversationId: c.id,
        role: 'assistant',
        text: 'new',
        createdAt: 2000,
        status: 'delivered',
      },
    ]
    store.hasMoreByConversationId[c.id] = true

    const prevFlag = (import.meta as any).env.VITE_BACKEND_HISTORY_SYNC
    ;(import.meta as any).env.VITE_BACKEND_HISTORY_SYNC = 'true'
    const spy = vi.spyOn(chatApi, 'fetchChatMessages').mockResolvedValue([
      {
        id: 'm-old',
        conversationId: c.id,
        role: 'user',
        text: 'old',
        createdAt: 1000,
        status: 'sent',
        meta: {},
      },
    ])

    await store.loadMore(c.id)
    expect(spy).toHaveBeenCalled()
    expect(store.messagesByConversationId[c.id][0].id).toBe('m-old')
    expect(store.messagesByConversationId[c.id][1].id).toBe('m-new')

    spy.mockRestore()
    ;(import.meta as any).env.VITE_BACKEND_HISTORY_SYNC = prevFlag
  })
})
