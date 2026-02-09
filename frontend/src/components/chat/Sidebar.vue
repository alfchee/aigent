<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

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
const deleteTargetId = ref<string | null>(null)
const isDeleteOpen = computed(() => deleteTargetId.value !== null)

function requestDelete(sessionId: string) {
  deleteTargetId.value = sessionId
}

function cancelDelete() {
  deleteTargetId.value = null
}

function confirmDelete() {
  if (!deleteTargetId.value) return
  emit('delete', deleteTargetId.value)
  deleteTargetId.value = null
}

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
    <Transition
      enter-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isDeleteOpen"
        class="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-label="Confirmación de eliminación"
        @click.self="cancelDelete"
      >
        <Transition
          enter-active-class="transition-all duration-300"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition-all duration-200"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div class="w-full max-w-sm rounded-2xl bg-white shadow-xl border border-slate-200 p-5">
            <div class="text-sm font-semibold text-slate-800 mb-2">¿Está seguro de que desea eliminar esta sesión?</div>
            <div class="text-xs text-slate-500 mb-4">Esta acción no se puede deshacer.</div>
            <div class="flex flex-col sm:flex-row gap-2 sm:justify-end">
              <button
                type="button"
                class="px-4 py-2 rounded-lg border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 transition-colors"
                @click="cancelDelete"
              >
                Cancelar
              </button>
              <button
                type="button"
                class="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
                @click="confirmDelete"
              >
                Confirmar
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
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
          class="text-xs px-2 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-red-600 hover:border-red-200 transition-colors"
          title="Eliminar sesión"
          @click.stop="requestDelete(s.id)"
        >
          ✕
        </button>
      </div>
    </div>
  </aside>
</template>
