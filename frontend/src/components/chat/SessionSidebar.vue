<script setup lang="ts">
import { computed } from 'vue'
import Button from '@/components/ui/Button.vue'
import IconButton from '@/components/ui/IconButton.vue'
import type { SessionSummaryDto } from '@/services/sessionsApi'
import { RefreshCw, FolderOpen, Tag, Trash2 } from 'lucide-vue-next'
import { AGENT_OPTIONS, findAgentById } from '@/config/agents'
import { cn } from '@/lib/utils'

const props = defineProps<{
  sessions: SessionSummaryDto[]
  activeSessionId: string
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  (e: 'select', sessionId: string): void
  (e: 'refresh'): void
  (e: 'rename', sessionId: string, title: string): void
  (e: 'remove', sessionId: string): void
  (e: 'setTags', sessionId: string, tags: string[]): void
  (e: 'setAgent', sessionId: string, agentId: string): void
  (e: 'setFolder', sessionId: string, folder: string): void
}>()

const items = computed(() => props.sessions)

function fmtDate(ts: number) {
  if (!ts) return 'sin actividad'
  return new Date(ts).toLocaleString()
}

function rename(session: SessionSummaryDto) {
  const next = window.prompt('Renombrar sesión', session.title || session.session_id)
  if (next == null) return
  emit('rename', session.session_id, next)
}

function remove(session: SessionSummaryDto) {
  const ok = window.confirm(
    '¿Eliminar sesión del servidor? Esta acción no se puede deshacer.',
  )
  if (!ok) return
  emit('remove', session.session_id)
}

function editTags(session: SessionSummaryDto) {
  const current = (session.tags ?? []).join(', ')
  const next = window.prompt('Tags (separados por coma)', current)
  if (next == null) return
  const tags = next
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
  emit('setTags', session.session_id, tags)
}

function editFolder(session: SessionSummaryDto) {
  const current = session.folder ?? 'General'
  const next = window.prompt('Carpeta', current)
  if (next == null) return
  emit('setFolder', session.session_id, next.trim())
}

function editAgent(session: SessionSummaryDto) {
  const current = session.agentId ?? 'default'
  const options = AGENT_OPTIONS.map((a) => `${a.id}: ${a.label}`).join('\n')
  const next = window.prompt(`Agente para esta sesión\n${options}`, current)
  if (next == null) return
  emit('setAgent', session.session_id, next.trim())
}
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="mb-2 flex items-center justify-between px-2 pt-2">
      <div class="text-xs font-semibold uppercase tracking-wide text-muted">
        Sesiones remotas
      </div>
      <Button variant="secondary" size="sm" class="h-7 px-2" @click="emit('refresh')">
        <RefreshCw :class="['h-3.5 w-3.5', loading ? 'animate-spin' : '']" />
      </Button>
    </div>

    <div
      v-if="error"
      class="mx-2 mb-2 rounded border border-danger/30 bg-danger/10 px-2 py-1 text-[11px] text-danger"
    >
      {{ error }}
    </div>

    <div class="grid gap-1">
      <button
        v-for="session in items"
        :key="session.session_id"
        type="button"
        class="group relative block w-full max-w-full overflow-hidden rounded-xl border px-3 py-3 text-left transition"
        :class="
          cn(
            session.session_id === activeSessionId
              ? 'border-brand/40 bg-brand/10'
              : 'border-transparent hover:border-border hover:bg-surface2/60',
          )
        "
        @click="emit('select', session.session_id)"
        @contextmenu.prevent="rename(session)"
      >
        <div class="flex max-w-full items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium">
              {{ session.title || session.session_id }}
            </div>
            <div class="mt-1 flex flex-wrap gap-1">
              <span
                class="inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-muted"
              >
                <FolderOpen class="h-3 w-3 shrink-0" />
                <span class="truncate">{{ session.folder ?? 'General' }}</span>
              </span>
              <span
                class="inline-flex max-w-full items-center rounded-full border border-brand/30 bg-brand/10 px-2 py-0.5 text-[11px] text-brand"
              >
                <span class="truncate"
                  >@{{ findAgentById(session.agentId ?? 'default').id }}</span
                >
              </span>
              <span
                v-for="t in session.tags ?? []"
                :key="t"
                class="inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-muted"
              >
                <Tag class="h-3 w-3 shrink-0" />
                <span class="truncate">{{ t }}</span>
              </span>
            </div>
          </div>
          <div
            class="flex shrink-0 items-center gap-0.5 opacity-0 transition group-hover:opacity-100 sm:gap-1"
          >
            <IconButton
              aria-label="Cambiar carpeta"
              size="sm"
              variant="ghost"
              @click.stop="editFolder(session)"
            >
              <FolderOpen class="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            </IconButton>
            <IconButton
              aria-label="Cambiar agente"
              size="sm"
              variant="ghost"
              @click.stop="editAgent(session)"
            >
              <span class="text-[10px] text-muted sm:text-xs">@</span>
            </IconButton>
            <IconButton
              aria-label="Editar tags"
              size="sm"
              variant="ghost"
              @click.stop="editTags(session)"
            >
              <Tag class="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            </IconButton>
            <IconButton
              aria-label="Renombrar"
              size="sm"
              variant="ghost"
              @click.stop="rename(session)"
            >
              <span class="text-[10px] text-muted sm:text-xs">Ren</span>
            </IconButton>
            <IconButton
              aria-label="Eliminar"
              size="sm"
              variant="danger"
              @click.stop="remove(session)"
            >
              <Trash2 class="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            </IconButton>
          </div>
        </div>
        <div class="mt-2 text-[11px] text-muted sm:text-xs">
          {{ fmtDate(session.last_activity) }} · {{ session.total_messages }} msg
        </div>
      </button>

      <div
        v-if="!loading && items.length === 0"
        class="py-4 text-center text-[11px] text-muted"
      >
        No hay sesiones remotas
      </div>
    </div>
  </div>
</template>
