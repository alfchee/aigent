import { openDB, type DBSchema } from 'idb'
import type { ChatMessage, Conversation } from '@/types/chat'

type StoredConversation = Conversation
type StoredMessage = ChatMessage

interface ChatDb extends DBSchema {
  conversations: {
    key: string
    value: StoredConversation
    indexes: { 'by-updatedAt': number }
  }
  messages: {
    key: string
    value: StoredMessage
    indexes: { 'by-conversation': string; 'by-conversation-createdAt': [string, number] }
  }
}

const DB_NAME = 'navibot-chat'
const DB_VERSION = 1

function safeClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export async function getDb() {
  return openDB<ChatDb>(DB_NAME, DB_VERSION, {
    upgrade(db) {
      const conv = db.createObjectStore('conversations', { keyPath: 'id' })
      conv.createIndex('by-updatedAt', 'updatedAt')

      const msgs = db.createObjectStore('messages', { keyPath: 'id' })
      msgs.createIndex('by-conversation', 'conversationId')
      msgs.createIndex('by-conversation-createdAt', ['conversationId', 'createdAt'])
    },
  })
}

export async function upsertConversation(c: StoredConversation) {
  const db = await getDb()
  await db.put('conversations', safeClone(c))
}

export async function deleteConversation(conversationId: string) {
  const db = await getDb()
  const tx = db.transaction(['conversations', 'messages'], 'readwrite')
  await tx.objectStore('conversations').delete(conversationId)

  const idx = tx.objectStore('messages').index('by-conversation')
  let cursor = await idx.openCursor(conversationId)
  while (cursor) {
    await cursor.delete()
    cursor = await cursor.continue()
  }
  await tx.done
}

export async function listConversations(limit = 200) {
  const db = await getDb()
  const idx = db.transaction('conversations').store.index('by-updatedAt')
  const out: StoredConversation[] = []
  let cursor = await idx.openCursor(null, 'prev')
  while (cursor && out.length < limit) {
    out.push(cursor.value)
    cursor = await cursor.continue()
  }
  return out
}

export async function upsertMessages(msgs: StoredMessage[]) {
  const db = await getDb()
  const tx = db.transaction('messages', 'readwrite')
  for (const m of msgs) await tx.store.put(safeClone(m))
  await tx.done
}

export async function listMessagesPage(opts: {
  conversationId: string
  beforeCreatedAt?: number
  pageSize: number
}) {
  const db = await getDb()
  const idx = db.transaction('messages').store.index('by-conversation-createdAt')

  const end = opts.beforeCreatedAt ?? Number.POSITIVE_INFINITY
  const range = IDBKeyRange.bound([opts.conversationId, 0], [opts.conversationId, end])

  const out: StoredMessage[] = []
  let cursor = await idx.openCursor(range, 'prev')
  while (cursor && out.length < opts.pageSize) {
    out.push(cursor.value)
    cursor = await cursor.continue()
  }
  return out.reverse()
}
