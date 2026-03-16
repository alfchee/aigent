<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ConversationList from '@/components/chat/ConversationList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import MessageList from '@/components/chat/MessageList.vue'
import IconButton from '@/components/ui/IconButton.vue'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import { useMessagesStore } from '@/stores/messages'
import { useWebSocketStore } from '@/stores/websocket'
import { usePreferencesStore } from '@/stores/preferences'
import { useUserConfigStore } from '@/stores/userConfig'
import { AGENT_OPTIONS, findAgentById } from '@/config/agents'
import {
  downloadText,
  exportConversationAsJson,
  exportConversationAsTxt,
} from '@/services/exportChat'
import { Share2, Download, Wifi, WifiOff, RotateCcw } from 'lucide-vue-next'

const router = useRouter()
const messages = useMessagesStore()
const ws = useWebSocketStore()
const prefs = usePreferencesStore()
const user = useUserConfigStore()

const showExport = ref(false)
const listRef = ref<InstanceType<typeof MessageList> | null>(null)

const activeId = computed(() => messages.activeConversationId)
const activeConv = computed(() => messages.activeConversation)
const activeMsgs = computed(() => messages.activeMessages)

const statusLabel = computed(() => {
  if (ws.status === 'open') return 'Conectado'
  if (ws.status === 'reconnecting' || ws.status === 'connecting') return 'Reintentando'
  if (ws.status === 'error') return 'Error'
  return 'Offline'
})

const statusIcon = computed(() => {
  if (ws.status === 'open') return Wifi
  if (ws.status === 'reconnecting' || ws.status === 'connecting') return RotateCcw
  return WifiOff
})

async function onSend(text: string) {
  if (!activeId.value) return

  if (text.startsWith('/new')) {
    await messages.createConversation()
    listRef.value?.scrollToBottom?.()
    return
  }
  if (text.startsWith('/export')) {
    showExport.value = true
    return
  }
  if (text.startsWith('/clear')) {
    return
  }
  if (text.startsWith('/folder')) {
    const folder = text.replace('/folder', '').trim()
    if (folder) await messages.setConversationFolder(activeId.value, folder)
    return
  }

  let finalText = text
  const mentionMatch = finalText.match(/^@([a-zA-Z0-9_-]+)\s+/)
  if (mentionMatch) {
    const candidate = mentionMatch[1]
    const exists = AGENT_OPTIONS.some((a) => a.id === candidate)
    if (exists) {
      await messages.setConversationAgent(activeId.value, candidate)
      user.setActiveAgentId(candidate)
      finalText = finalText.slice(mentionMatch[0].length).trim()
      if (!finalText) return
    }
  }

  messages.setAssistantTyping(activeId.value, true)
  const msg = await messages.addMessage({
    conversationId: activeId.value,
    role: 'user',
    text: finalText,
    status: 'sending',
  })

  const out = {
    type: 'user_message' as const,
    sessionId: user.sessionId,
    conversationId: activeId.value,
    messageId: msg.id,
    text: msg.text,
    createdAt: msg.createdAt,
    agentId: activeConv.value?.agentId ?? user.activeAgentId,
    e2ee: prefs.e2eeEnabled,
  }

  const res = ws.send(out)
  if (!res.ok) {
    await messages.updateMessageStatus(activeId.value, msg.id, 'error')
    messages.setAssistantTyping(activeId.value, false)
    return
  }
  await messages.updateMessageStatus(activeId.value, msg.id, res.queued ? 'sent' : 'sent')
  listRef.value?.scrollToBottom?.()
}

function openSettings() {
  router.push('/settings')
}

function exportJson() {
  if (!activeConv.value || !activeId.value) return
  const json = exportConversationAsJson(activeConv.value, activeMsgs.value)
  downloadText(`chat-${activeConv.value.id}.json`, json)
  showExport.value = false
}

function exportTxt() {
  if (!activeConv.value || !activeId.value) return
  const txt = exportConversationAsTxt(activeConv.value, activeMsgs.value)
  downloadText(`chat-${activeConv.value.id}.txt`, txt)
  showExport.value = false
}

async function shareConversation() {
  if (!activeConv.value || !activeId.value) return
  const txt = exportConversationAsTxt(activeConv.value, activeMsgs.value)
  if (navigator.share) {
    await navigator.share({ title: activeConv.value.title, text: txt })
  } else {
    await navigator.clipboard.writeText(txt)
  }
}

onMounted(async () => {
  await messages.bootstrap()
  ws.connect()
})

watch(
  () => messages.activeConversationId,
  () => {
    listRef.value?.scrollToBottom?.()
  },
)
</script>

<template>
  <div data-testid="chat-page-root" class="h-[100dvh] max-h-[100dvh] overflow-hidden">
    <div class="grid h-full grid-cols-12 overflow-hidden">
      <aside
        class="col-span-12 h-full overflow-hidden border-r border-border bg-surface md:col-span-4 lg:col-span-3"
        :class="
          prefs.sidebarCollapsed ? 'hidden md:block md:col-span-1 lg:col-span-1' : ''
        "
      >
        <ConversationList
          :conversations="messages.conversations"
          :active-id="messages.activeConversationId"
          @create="messages.createConversation"
          @select="messages.setActiveConversation"
          @rename="messages.renameConversation"
          @set-tags="messages.setTags"
          @set-agent="messages.setConversationAgent"
          @set-folder="messages.setConversationFolder"
          @remove="messages.removeConversation"
          @open-settings="openSettings"
        />
      </aside>

      <main
        class="col-span-12 flex h-full min-h-0 flex-col overflow-hidden md:col-span-8 lg:col-span-9"
      >
        <div
          class="shrink-0 flex items-center justify-between border-b border-border bg-bg px-4 py-3"
        >
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold">
              {{ activeConv?.title ?? 'Chat' }}
            </div>
            <div class="mt-1 flex items-center gap-2 text-xs text-muted">
              <span
                class="inline-flex items-center rounded-full border border-border px-2 py-0.5"
              >
                {{ activeConv?.folder ?? 'General' }}
              </span>
              <span
                class="inline-flex items-center rounded-full border border-brand/30 px-2 py-0.5 text-brand"
              >
                @{{ findAgentById(activeConv?.agentId ?? user.activeAgentId).id }}
              </span>
              <component :is="statusIcon" class="h-3.5 w-3.5" />
              <span>{{ statusLabel }}</span>
              <span v-if="ws.latencyMs != null">· {{ ws.latencyMs }}ms</span>
              <span v-if="ws.lastError" class="text-danger">· {{ ws.lastError }}</span>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <IconButton
              aria-label="Compartir"
              size="sm"
              variant="ghost"
              @click="shareConversation"
            >
              <Share2 class="h-4 w-4" />
            </IconButton>
            <IconButton
              aria-label="Exportar"
              size="sm"
              variant="ghost"
              @click="showExport = true"
            >
              <Download class="h-4 w-4" />
            </IconButton>
          </div>
        </div>

        <div v-if="activeId" class="min-h-0 flex-1 overflow-hidden">
          <MessageList ref="listRef" :conversation-id="activeId" />
        </div>
        <div
          v-else
          class="flex flex-1 items-center justify-center p-8 text-sm text-muted"
        >
          Crea o selecciona una conversación
        </div>

        <div class="shrink-0 border-t border-border bg-bg p-4">
          <ChatInput @send="onSend" />
          <div
            v-if="ws.status !== 'open' && ws.outbox.length"
            class="mt-3 rounded-xl border border-border bg-surface px-3 py-2 text-xs text-muted"
          >
            {{ ws.outbox.length }} mensaje(s) en cola; se enviarán al reconectar.
          </div>
        </div>
      </main>
    </div>

    <Modal :open="showExport" title="Exportar conversación" @close="showExport = false">
      <div class="grid gap-3">
        <div class="text-sm text-muted">Elige un formato de exportación.</div>
        <div class="flex flex-col gap-2 sm:flex-row">
          <Button variant="primary" class="flex-1" @click="exportJson">JSON</Button>
          <Button variant="secondary" class="flex-1" @click="exportTxt">TXT</Button>
        </div>
      </div>
    </Modal>
  </div>
</template>
