import { defineStore } from 'pinia'
import type { ChatMessage, Conversation, MessageStatus, MessageRole } from '@/types/chat'
import {
  listConversations,
  listMessagesPage,
  upsertConversation,
  upsertMessages,
  deleteConversation as dbDeleteConversation,
} from '@/services/storage'
import { fetchChatMessages } from '@/services/chatApi'
import { mergeChatMessageLists } from '@/services/chatSync'
import { sanitizeText } from '@/services/sanitize'
import { useUserConfigStore } from '@/stores/userConfig'

type MessagesState = {
  conversations: Conversation[]
  activeConversationId: string | null
  messagesByConversationId: Record<string, ChatMessage[]>
  hasMoreByConversationId: Record<string, boolean>
  loadingMore: boolean
  assistantTypingByConversationId: Record<string, boolean>
}

function shouldSyncBackendHistory() {
  return (import.meta.env.VITE_BACKEND_HISTORY_SYNC as string | undefined) === 'true'
}

const PAGE_SIZE = 40

function buildConversationFromMessages(
  conversationId: string,
  messages: ChatMessage[],
): Conversation {
  const sorted = [...messages].sort((a, b) => a.createdAt - b.createdAt)
  const firstUser = sorted.find((m) => m.role === 'user')
  const last = sorted[sorted.length - 1]
  const now = Date.now()
  const title =
    (firstUser?.text ?? sorted[0]?.text ?? 'Conversación').slice(0, 28) || 'Conversación'
  return {
    id: conversationId,
    title,
    createdAt: sorted[0]?.createdAt ?? now,
    updatedAt: last?.createdAt ?? now,
    tags: [],
    folder: 'General',
    agentId: 'default',
  }
}

function newConversation(): Conversation {
  const user = useUserConfigStore()
  const now = Date.now()
  return {
    id: crypto.randomUUID(),
    title: 'Nueva conversación',
    createdAt: now,
    updatedAt: now,
    tags: [],
    agentId: user.activeAgentId,
    folder: 'General',
  }
}

export const useMessagesStore = defineStore('messages', {
  state: (): MessagesState => ({
    conversations: [],
    activeConversationId: null,
    messagesByConversationId: {},
    hasMoreByConversationId: {},
    loadingMore: false,
    assistantTypingByConversationId: {},
  }),
  getters: {
    activeConversation(state) {
      return state.conversations.find((c) => c.id === state.activeConversationId) ?? null
    },
    activeMessages(state) {
      if (!state.activeConversationId) return []
      return state.messagesByConversationId[state.activeConversationId] ?? []
    },
  },
  actions: {
    mergeMessages(conversationId: string, incoming: ChatMessage[]) {
      const current = this.messagesByConversationId[conversationId] ?? []
      const merged = mergeChatMessageLists(current, incoming)
      this.messagesByConversationId[conversationId] = merged
      return merged
    },
    async bootstrapFromBackend(sessionId: string) {
      const remote = await fetchChatMessages({ sessionId, limit: 200 })
      if (!remote.length) return false
      const grouped: Record<string, ChatMessage[]> = {}
      for (const msg of remote) {
        if (!grouped[msg.conversationId]) grouped[msg.conversationId] = []
        grouped[msg.conversationId].push(msg)
      }
      const conversations = Object.entries(grouped).map(([conversationId, msgs]) =>
        buildConversationFromMessages(conversationId, msgs),
      )
      conversations.sort((a, b) => b.updatedAt - a.updatedAt)
      this.conversations = conversations
      this.activeConversationId = conversations[0]?.id ?? null
      for (const conv of conversations) {
        const merged = this.mergeMessages(conv.id, grouped[conv.id] ?? [])
        this.hasMoreByConversationId[conv.id] = merged.length >= PAGE_SIZE
        await upsertConversation(conv)
        await upsertMessages(merged)
      }
      return conversations.length > 0
    },
    async hydrateConversationFromBackend(sessionId: string, conversationId: string) {
      const remote = await fetchChatMessages({
        sessionId,
        conversationId,
        limit: PAGE_SIZE,
      })
      if (!remote.length) return
      const merged = this.mergeMessages(conversationId, remote)
      this.hasMoreByConversationId[conversationId] = remote.length === PAGE_SIZE
      await upsertMessages(merged)
      const idx = this.conversations.findIndex((c) => c.id === conversationId)
      if (idx >= 0) {
        const conv = {
          ...this.conversations[idx],
          updatedAt: merged[merged.length - 1]?.createdAt ?? Date.now(),
        }
        this.conversations.splice(idx, 1, conv)
        await upsertConversation(conv)
      }
    },
    async bootstrap() {
      const user = useUserConfigStore()
      const convs = await listConversations()
      this.conversations = convs

      if (!this.conversations.length && shouldSyncBackendHistory()) {
        try {
          const synced = await this.bootstrapFromBackend(user.sessionId)
          if (synced) return
        } catch {}
      }

      if (!this.conversations.length) {
        const c = newConversation()
        this.conversations = [c]
        await upsertConversation(c)
      }

      if (!this.activeConversationId) {
        this.activeConversationId = this.conversations[0].id
      }

      await this.ensureMessagesLoaded(this.activeConversationId)
      if (shouldSyncBackendHistory()) {
        try {
          await this.hydrateConversationFromBackend(
            user.sessionId,
            this.activeConversationId,
          )
        } catch {}
      }
    },
    async ensureMessagesLoaded(conversationId: string) {
      if (this.messagesByConversationId[conversationId]?.length) return
      const localPage = await listMessagesPage({ conversationId, pageSize: PAGE_SIZE })
      let merged = this.mergeMessages(conversationId, localPage)
      let hasMore = localPage.length === PAGE_SIZE
      if (shouldSyncBackendHistory()) {
        const user = useUserConfigStore()
        try {
          const remotePage = await fetchChatMessages({
            sessionId: user.sessionId,
            conversationId,
            limit: PAGE_SIZE,
          })
          merged = this.mergeMessages(conversationId, remotePage)
          hasMore = remotePage.length === PAGE_SIZE || hasMore
          await upsertMessages(merged)
        } catch {}
      }
      this.messagesByConversationId[conversationId] = merged
      this.hasMoreByConversationId[conversationId] = hasMore
    },
    async loadMore(conversationId: string) {
      if (this.loadingMore) return
      if (!this.hasMoreByConversationId[conversationId]) return

      const current = this.messagesByConversationId[conversationId] ?? []
      const before = current.length ? current[0].createdAt : undefined
      this.loadingMore = true
      try {
        if (shouldSyncBackendHistory()) {
          const user = useUserConfigStore()
          try {
            const remotePage = await fetchChatMessages({
              sessionId: user.sessionId,
              conversationId,
              beforeCreatedAt: before,
              limit: PAGE_SIZE,
            })
            const merged = this.mergeMessages(conversationId, remotePage)
            this.messagesByConversationId[conversationId] = merged
            this.hasMoreByConversationId[conversationId] = remotePage.length === PAGE_SIZE
            await upsertMessages(merged)
            return
          } catch {}
        }
        const localPage = await listMessagesPage({
          conversationId,
          pageSize: PAGE_SIZE,
          beforeCreatedAt: before,
        })
        this.messagesByConversationId[conversationId] = mergeChatMessageLists(
          localPage,
          current,
        )
        this.hasMoreByConversationId[conversationId] = localPage.length === PAGE_SIZE
      } finally {
        this.loadingMore = false
      }
    },
    async createConversation() {
      const c = newConversation()
      this.conversations = [c, ...this.conversations]
      this.activeConversationId = c.id
      await upsertConversation(c)
      this.messagesByConversationId[c.id] = []
      this.hasMoreByConversationId[c.id] = false
      return c
    },
    async setActiveConversation(id: string) {
      this.activeConversationId = id
      await this.ensureMessagesLoaded(id)
      this.setAssistantTyping(id, false)
      this.markAllRead(id)
    },
    async renameConversation(id: string, title: string) {
      const clean = sanitizeText(title).slice(0, 80).trim() || 'Conversación'
      const idx = this.conversations.findIndex((c) => c.id === id)
      if (idx < 0) return
      const updated: Conversation = {
        ...this.conversations[idx],
        title: clean,
        updatedAt: Date.now(),
      }
      this.conversations.splice(idx, 1, updated)
      await upsertConversation(updated)
    },
    async setTags(id: string, tags: string[]) {
      const idx = this.conversations.findIndex((c) => c.id === id)
      if (idx < 0) return
      const cleanTags = tags
        .map((t) => sanitizeText(t).slice(0, 24).trim())
        .filter(Boolean)
        .slice(0, 8)
      const updated: Conversation = {
        ...this.conversations[idx],
        tags: cleanTags,
        updatedAt: Date.now(),
      }
      this.conversations.splice(idx, 1, updated)
      await upsertConversation(updated)
    },
    async setConversationAgent(id: string, agentId: string) {
      const idx = this.conversations.findIndex((c) => c.id === id)
      if (idx < 0) return
      const cleanAgentId = sanitizeText(agentId).slice(0, 40).trim() || 'default'
      const updated: Conversation = {
        ...this.conversations[idx],
        agentId: cleanAgentId,
        updatedAt: Date.now(),
      }
      this.conversations.splice(idx, 1, updated)
      await upsertConversation(updated)
    },
    async setConversationFolder(id: string, folder: string) {
      const idx = this.conversations.findIndex((c) => c.id === id)
      if (idx < 0) return
      const cleanFolder = sanitizeText(folder).slice(0, 40).trim() || 'General'
      const updated: Conversation = {
        ...this.conversations[idx],
        folder: cleanFolder,
        updatedAt: Date.now(),
      }
      this.conversations.splice(idx, 1, updated)
      await upsertConversation(updated)
    },
    async removeConversation(id: string) {
      const next = this.conversations.filter((c) => c.id !== id)
      this.conversations = next
      delete this.messagesByConversationId[id]
      delete this.hasMoreByConversationId[id]
      delete this.assistantTypingByConversationId[id]
      await dbDeleteConversation(id)

      if (this.activeConversationId === id) {
        if (!this.conversations.length) {
          const c = await this.createConversation()
          this.activeConversationId = c.id
        } else {
          await this.setActiveConversation(this.conversations[0].id)
        }
      }
    },
    async addMessage(input: {
      conversationId: string
      role: MessageRole
      text: string
      status: MessageStatus
      id?: string
      createdAt?: number
      meta?: Record<string, unknown>
    }) {
      const now = Date.now()
      const msg: ChatMessage = {
        id: input.id ?? crypto.randomUUID(),
        conversationId: input.conversationId,
        role: input.role,
        text: sanitizeText(input.text).slice(0, 20_000),
        createdAt: input.createdAt ?? now,
        status: input.status,
        meta: input.meta,
      }

      const list = this.messagesByConversationId[msg.conversationId] ?? []
      this.messagesByConversationId[msg.conversationId] = mergeChatMessageLists(list, [
        msg,
      ])

      const cIdx = this.conversations.findIndex((c) => c.id === msg.conversationId)
      if (cIdx >= 0) {
        const prev = this.conversations[cIdx]
        const next: Conversation = { ...prev, updatedAt: now }
        if (prev.title === 'Nueva conversación' && msg.role === 'user') {
          next.title = msg.text.slice(0, 28) || prev.title
        }
        this.conversations.splice(cIdx, 1)
        this.conversations.unshift(next)
        await upsertConversation(next)
      }

      await upsertMessages([msg])
      return msg
    },
    async updateMessageStatus(
      conversationId: string,
      messageId: string,
      status: MessageStatus,
    ) {
      const list = this.messagesByConversationId[conversationId] ?? []
      const idx = list.findIndex((m) => m.id === messageId)
      if (idx < 0) return
      const updated = { ...list[idx], status }
      const next = list.slice()
      next.splice(idx, 1, updated)
      this.messagesByConversationId[conversationId] = next
      await upsertMessages([updated])
    },
    markAllRead(conversationId: string) {
      const list = this.messagesByConversationId[conversationId] ?? []
      const changed = list.map((m) =>
        m.status === 'delivered' && m.role !== 'user'
          ? { ...m, status: 'read' as const }
          : m,
      )
      this.messagesByConversationId[conversationId] = changed
      upsertMessages(changed).catch(() => {})
    },
    setAssistantTyping(conversationId: string, typing: boolean) {
      this.assistantTypingByConversationId[conversationId] = typing
    },
  },
})
