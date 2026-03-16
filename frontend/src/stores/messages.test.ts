import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useMessagesStore } from './messages'

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
})
