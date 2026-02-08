<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useSessionsStore } from '../../stores/sessions'
import { isCollapsed as isCollapsedState, nextSidebarState, sidebarWidthPx, type SidebarState } from '../../lib/sidebars'

const props = defineProps<{
  activeSessionId: string
  sidebarState: SidebarState
}>()

const emit = defineEmits<{
  (e: 'select', sessionId: string): void
  (e: 'new'): void
  (e: 'delete', sessionId: string): void
  (e: 'toggle'): void
}>()

const sessions = useSessionsStore()

const items = computed(() => sessions.sessions)
const loading = computed(() => sessions.loading)
const error = computed(() => sessions.error)
const collapsed = computed(() => isCollapsedState(props.sidebarState))
const widthPx = computed(() => sidebarWidthPx(props.sidebarState))
const nextStateLabel = computed(() => nextSidebarState(props.sidebarState))

onMounted(() => {
  sessions.fetchSessions()
})
</script>

<template>
  <aside
    data-testid="sessions-sidebar"
    class="h-full border-r border-slate-200 bg-white flex flex-col transition-all duration-300"
    :style="{ width: widthPx + 'px' }"
  >
    <div class="p-3 border-b border-slate-200 flex items-center justify-between gap-2">
      <div v-if="!collapsed" class="text-xs font-semibold text-slate-700 uppercase tracking-widest">Sesiones</div>
      <div v-else class="text-[10px] font-semibold text-slate-600 uppercase tracking-widest truncate" title="Sesiones">
        Ses.
      </div>
      <button
        type="button"
        class="text-xs px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50"
        :title="`Cambiar tamaño: ${nextStateLabel}`"
        @click="emit('toggle')"
      >
        ↔
      </button>
      <button
        v-if="!collapsed"
        type="button"
        class="text-xs px-2 py-1 rounded bg-sky-600 text-white hover:bg-sky-700"
        @click="emit('new')"
      >
        New
      </button>
    </div>

    <div v-if="error" class="p-3 text-xs text-red-600">
      {{ error }}
    </div>

    <div v-if="loading" class="p-3 text-xs text-slate-500">Cargando…</div>

    <div v-else class="flex-1 min-h-0 overflow-y-auto">
      <div
        v-for="s in items"
        :key="s.id"
        class="w-full text-left px-3 py-2 border-b border-slate-100 hover:bg-slate-50 flex items-center justify-between gap-2 cursor-pointer"
        :class="s.id === props.activeSessionId ? 'bg-sky-50' : ''"
        role="button"
        tabindex="0"
        @click="emit('select', s.id)"
      >
        <div class="min-w-0">
          <div v-if="!collapsed" class="text-sm font-medium text-slate-800 truncate">
            {{ s.title || 'Nueva Conversación' }}
          </div>
          <div v-else class="text-sm font-medium text-slate-800 truncate" :title="s.title || 'Nueva Conversación'">💬</div>
          <div v-if="!collapsed" class="text-[10px] text-slate-500 font-mono truncate">
            {{ s.id }}
          </div>
        </div>
        <button
          v-if="!collapsed"
          type="button"
          class="text-xs px-2 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
          @click.stop="emit('delete', s.id)"
        >
          ✕
        </button>
      </div>
    </div>
  </aside>
</template>
