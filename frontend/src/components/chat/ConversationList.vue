<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Conversation } from '@/types/chat'
import Button from '@/components/ui/Button.vue'
import IconButton from '@/components/ui/IconButton.vue'
import {
  Plus,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Tag,
} from 'lucide-vue-next'
import { cn } from '@/lib/utils'
import { usePreferencesStore } from '@/stores/preferences'

const props = defineProps<{ conversations: Conversation[]; activeId: string | null }>()
const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'create'): void
  (e: 'rename', id: string, title: string): void
  (e: 'remove', id: string): void
  (e: 'setTags', id: string, tags: string[]): void
  (e: 'openSettings'): void
}>()

const prefs = usePreferencesStore()
const q = ref('')

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return props.conversations
  return props.conversations.filter((c) => {
    if (c.title.toLowerCase().includes(s)) return true
    return c.tags.some((t) => t.toLowerCase().includes(s))
  })
})

function rename(conv: Conversation) {
  const next = window.prompt('Renombrar conversación', conv.title)
  if (next == null) return
  emit('rename', conv.id, next)
}

function editTags(conv: Conversation) {
  const current = conv.tags.join(', ')
  const next = window.prompt('Tags (separados por coma)', current)
  if (next == null) return
  const tags = next
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
  emit('setTags', conv.id, tags)
}

function remove(conv: Conversation) {
  const ok = window.confirm('¿Borrar conversación? Esta acción no se puede deshacer.')
  if (!ok) return
  emit('remove', conv.id)
}
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
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-2 pb-4">
      <div class="grid gap-1">
        <button
          v-for="c in filtered"
          :key="c.id"
          type="button"
          class="group rounded-xl border px-3 py-3 text-left transition"
          :class="
            cn(
              c.id === activeId
                ? 'border-brand/40 bg-brand/10'
                : 'border-transparent hover:border-border hover:bg-surface2/60',
            )
          "
          @click="emit('select', c.id)"
          @contextmenu.prevent="rename(c)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="truncate text-sm font-medium">{{ c.title }}</div>
              <div class="mt-1 flex flex-wrap gap-1">
                <span
                  v-for="t in c.tags"
                  :key="t"
                  class="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-muted"
                >
                  <Tag class="h-3 w-3" />
                  {{ t }}
                </span>
              </div>
            </div>
            <div
              class="flex shrink-0 items-center gap-1 opacity-0 transition group-hover:opacity-100"
            >
              <IconButton
                aria-label="Editar tags"
                size="sm"
                variant="ghost"
                @click.stop="editTags(c)"
              >
                <Tag class="h-4 w-4" />
              </IconButton>
              <IconButton
                aria-label="Renombrar"
                size="sm"
                variant="ghost"
                @click.stop="rename(c)"
              >
                <span class="text-xs text-muted">Ren</span>
              </IconButton>
              <IconButton
                aria-label="Borrar"
                size="sm"
                variant="danger"
                @click.stop="remove(c)"
              >
                <span class="text-xs">Del</span>
              </IconButton>
            </div>
          </div>
          <div class="mt-2 text-xs text-muted">
            {{ new Date(c.updatedAt).toLocaleString() }}
          </div>
        </button>
      </div>
    </div>
  </div>
</template>
