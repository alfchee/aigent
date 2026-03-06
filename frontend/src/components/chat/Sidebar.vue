<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useSessionsStore } from '../../stores/sessions'
import {
  isCollapsed as isCollapsedState,
  nextSidebarState,
  sidebarWidthPx,
  type SidebarState,
} from '../../lib/sidebars'

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
          <div
            v-if="isDeleteOpen"
            class="w-full max-w-sm rounded-2xl bg-white shadow-xl border border-slate-200 p-5"
          >
            <div class="text-sm font-semibold text-slate-800 mb-2">
              ¿Está seguro de que desea eliminar esta sesión?
            </div>
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
    <div class="p-4 border-b border-slate-200 flex items-center justify-between">
      <div v-if="!collapsed" class="text-xs font-bold text-slate-500 uppercase tracking-wider">
        Sesiones
      </div>
      <div
        v-else
        class="text-[10px] font-bold text-slate-500 uppercase tracking-wider truncate"
        title="Sesiones"
      >
        Ses.
      </div>
      <div class="flex gap-2">
        <button
          type="button"
          class="p-1 text-slate-400 hover:text-sky-500 transition-colors"
          :title="`Cambiar tamaño: ${nextStateLabel}`"
          @click="emit('toggle')"
        >
          <span class="material-icons-outlined text-lg">compare_arrows</span>
        </button>
        <button
          v-if="!collapsed"
          type="button"
          class="bg-sky-500 hover:bg-sky-600 text-white text-xs px-3 py-1 rounded shadow-sm font-medium transition-colors flex items-center gap-1"
          @click="emit('new')"
        >
          <span class="material-icons-outlined text-xs">add</span> New
        </button>
      </div>
    </div>

    <div v-if="error" class="p-3 text-xs text-red-600">
      {{ error }}
    </div>

    <div v-if="loading" class="p-3 text-xs text-slate-500">Cargando…</div>

    <div v-else class="flex-1 overflow-y-auto p-2 space-y-1">
      <div
        v-for="s in items"
        :key="s.id"
        class="group session-item flex items-center p-3 rounded-lg cursor-pointer transition-colors"
        :class="[
          s.id === props.activeSessionId
            ? 'bg-sky-50 border border-sky-100'
            : 'hover:bg-gray-100 border border-transparent',
          collapsed ? 'session-item-collapsed justify-center' : '',
        ]"
        :data-tooltip="collapsed ? s.title || 'Nueva Conversación' : ''"
        :aria-label="collapsed ? s.title || 'Nueva Conversación' : undefined"
        role="button"
        tabindex="0"
        @click="emit('select', s.id)"
      >
        <div :class="['flex-1 min-w-0', collapsed ? 'pr-0' : 'pr-2']">
          <div v-if="!collapsed">
            <h3 class="text-sm font-medium text-slate-900 truncate">
              {{ s.title || 'Nueva Conversación' }}
            </h3>
            <p class="text-xs text-slate-500 truncate mt-0.5 font-mono">{{ s.id }}</p>
          </div>
          <div v-else class="flex items-center justify-center">
            <span class="material-icons-outlined text-2xl leading-6 text-slate-600"
              >chat_bubble_outline</span
            >
          </div>
        </div>
        <button
          v-if="!collapsed"
          type="button"
          class="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-50 hover:text-red-500 rounded text-slate-400 transition-all"
          title="Eliminar sesión"
          @click.stop="requestDelete(s.id)"
        >
          <span class="material-icons-outlined text-sm">delete_outline</span>
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.session-item {
  position: relative;
}
.session-item-collapsed::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%) translateX(6px);
  background: #1f2937;
  color: #f9fafb;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 0.75rem;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
  transition-delay: 0s;
  z-index: 20;
}
.session-item-collapsed:hover::after {
  opacity: 1;
  transform: translateY(-50%) translateX(0);
  transition-delay: 0.5s;
}
</style>
