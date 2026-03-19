import { describe, expect, it } from 'vitest'
import { mergeChatMessageLists, reconcileMessageStatus } from '@/services/chatSync'

describe('chatSync', () => {
  it('prioriza estado no-error sobre error', () => {
    expect(reconcileMessageStatus('error', 'delivered')).toBe('delivered')
    expect(reconcileMessageStatus('sent', 'error')).toBe('sent')
  })

  it('fusiona listas por id y conserva orden cronológico', () => {
    const merged = mergeChatMessageLists(
      [
        {
          id: 'm2',
          conversationId: 'c1',
          role: 'assistant',
          text: 'dos',
          createdAt: 2000,
          status: 'delivered',
        },
      ],
      [
        {
          id: 'm1',
          conversationId: 'c1',
          role: 'user',
          text: 'uno',
          createdAt: 1000,
          status: 'sent',
        },
        {
          id: 'm2',
          conversationId: 'c1',
          role: 'assistant',
          text: 'dos',
          createdAt: 2000,
          status: 'read',
        },
      ],
    )
    expect(merged.map((x) => x.id)).toEqual(['m1', 'm2'])
    expect(merged[1].status).toBe('read')
  })
})
