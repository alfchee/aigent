import type { ChatMessage, MessageStatus } from '@/types/chat'

const STATUS_ORDER: MessageStatus[] = ['sending', 'sent', 'delivered', 'read']

function statusRank(status: MessageStatus) {
  const rank = STATUS_ORDER.indexOf(status)
  if (rank >= 0) return rank
  return -1
}

export function reconcileMessageStatus(
  current: MessageStatus,
  incoming: MessageStatus,
): MessageStatus {
  if (current === incoming) return current
  if (current === 'error' && incoming !== 'error') return incoming
  if (incoming === 'error' && current !== 'error') return current
  return statusRank(incoming) >= statusRank(current) ? incoming : current
}

export function mergeChatMessageLists(
  current: ChatMessage[],
  incoming: ChatMessage[],
): ChatMessage[] {
  const byId = new Map<string, ChatMessage>()
  for (const item of current) byId.set(item.id, item)
  for (const item of incoming) {
    const existing = byId.get(item.id)
    if (!existing) {
      byId.set(item.id, item)
      continue
    }
    byId.set(item.id, {
      ...existing,
      ...item,
      status: reconcileMessageStatus(existing.status, item.status),
      text: item.text || existing.text,
      createdAt: existing.createdAt ?? item.createdAt,
      meta: { ...(existing.meta ?? {}), ...(item.meta ?? {}) },
    })
  }
  return [...byId.values()].sort((a, b) => a.createdAt - b.createdAt)
}
