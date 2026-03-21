<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { Conversation } from '@/types/chat'
import Button from '@/components/ui/Button.vue'
import IconButton from '@/components/ui/IconButton.vue'
import SessionSidebar from '@/components/chat/SessionSidebar.vue'
import { Plus, Search, PanelLeftClose, PanelLeftOpen, Settings } from 'lucide-vue-next'
import { usePreferencesStore } from '@/stores/preferences'
import { AGENT_OPTIONS } from '@/config/agents'

const props = withDefaults(
  defineProps<{
    conversations: Conversation[]
    activeId: string | null
    sessions: import('@/services/sessionsApi').SessionSummaryDto[]
    activeSessionId: string
    sessionsLoading?: boolean
    sessionsError?: string | null
    showItems?: boolean
  }>(),
  {
    showItems: true,
    sessionsLoading: false,
    sessionsError: null,
  },
)

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'create'): void
  (e: 'openSettings'): void
  (e: 'selectSession', sessionId: string): void
  (e: 'refreshSessions'): void
  (e: 'renameSession', sessionId: string, title: string): void
  (e: 'removeSession', sessionId: string): void
  (e: 'setSessionTags', sessionId: string, tags: string[]): void
  (e: 'setSessionAgent', sessionId: string, agentId: string): void
  (e: 'setSessionFolder', sessionId: string, folder: string): void
}>()

const prefs = usePreferencesStore()
const q = ref('')
const folderFilter = ref('all')
const agentFilter = ref('all')
const FILTERS_KEY = 'navibot:conversation-filters'

function readFilters() {
  try {
    const raw = localStorage.getItem(FILTERS_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as { folder?: string; agent?: string }
    folderFilter.value = parsed.folder || 'all'
    agentFilter.value = parsed.agent || 'all'
  } catch {
    folderFilter.value = 'all'
    agentFilter.value = 'all'
  }
}

function persistFilters() {
  localStorage.setItem(
    FILTERS_KEY,
    JSON.stringify({ folder: folderFilter.value, agent: agentFilter.value }),
  )
}

const filteredSessions = computed(() => {
  const s = q.value.trim().toLowerCase()
  const base = props.sessions.filter((c) => {
    if (folderFilter.value !== 'all' && (c.folder ?? 'General') !== folderFilter.value) {
      return false
    }
    if (agentFilter.value !== 'all' && (c.agentId ?? 'default') !== agentFilter.value) {
      return false
    }
    return true
  })
  if (!s) return base
  return base.filter((c) => {
    if ((c.folder ?? 'General').toLowerCase().includes(s)) return true
    if ((c.agentId ?? 'default').toLowerCase().includes(s)) return true
    if ((c.title || c.session_id).toLowerCase().includes(s)) return true
    return (c.tags ?? []).some((t) => t.toLowerCase().includes(s))
  })
})

const folderOptions = computed(() => {
  const set = new Set<string>(['General'])
  for (const c of props.sessions) set.add(c.folder ?? 'General')
  return [...set]
})

watch([folderFilter, agentFilter], persistFilters)

onMounted(readFilters)
</script>

<template>
  <div class="flex h-full min-h-0 flex-col">
    <div class="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
      <div class="flex items-center gap-2">
        <IconButton
          :aria-label="prefs.sidebarCollapsed ? 'Expandir sidebar' : 'Colapsar sidebar'"
          size="sm"
          variant="ghost"
          @click="prefs.toggleSidebar"
        >
          <PanelLeftOpen v-if="prefs.sidebarCollapsed" class="h-4 w-4" />
          <PanelLeftClose v-else class="h-4 w-4" />
        </IconButton>
        <div class="text-sm font-semibold">Conversaciones</div>
      </div>
      <IconButton
        aria-label="Abrir ajustes"
        size="sm"
        variant="ghost"
        @click="emit('openSettings')"
      >
        <Settings class="h-4 w-4" />
      </IconButton>
    </div>

    <div class="p-4">
      <Button variant="primary" size="md" class="w-full" @click="emit('create')">
        <Plus class="h-4 w-4" />
        Nueva
      </Button>

      <div
        class="mt-3 flex items-center gap-2 rounded-xl border border-border bg-bg px-3"
      >
        <Search class="h-4 w-4 text-muted" />
        <input
          v-model="q"
          class="h-10 w-full bg-transparent text-sm outline-none"
          placeholder="Buscar…"
          aria-label="Buscar conversaciones"
        />
      </div>

      <div class="mt-2 grid grid-cols-2 gap-2">
        <select
          v-model="folderFilter"
          class="h-9 rounded-lg border border-border bg-bg px-2 text-xs outline-none"
          aria-label="Filtrar por carpeta"
        >
          <option value="all">Carpeta: todas</option>
          <option v-for="folder in folderOptions" :key="folder" :value="folder">
            {{ folder }}
          </option>
        </select>
        <select
          v-model="agentFilter"
          class="h-9 rounded-lg border border-border bg-bg px-2 text-xs outline-none"
          aria-label="Filtrar por agente"
        >
          <option value="all">Agente: todos</option>
          <option v-for="agent in AGENT_OPTIONS" :key="agent.id" :value="agent.id">
            @{{ agent.id }}
          </option>
        </select>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-2 pb-4">
      <SessionSidebar
        :sessions="filteredSessions"
        :active-session-id="activeSessionId"
        :loading="sessionsLoading"
        :error="sessionsError"
        @select="(id) => emit('selectSession', id)"
        @refresh="() => emit('refreshSessions')"
        @rename="(id, t) => emit('renameSession', id, t)"
        @remove="(id) => emit('removeSession', id)"
        @set-tags="(id, t) => emit('setSessionTags', id, t)"
        @set-folder="(id, f) => emit('setSessionFolder', id, f)"
        @set-agent="(id, a) => emit('setSessionAgent', id, a)"
      />
    </div>
  </div>
</template>
