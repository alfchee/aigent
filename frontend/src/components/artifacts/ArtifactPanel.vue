<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { useArtifactsStore } from '../../stores/artifacts'
import { useChatStore } from '../../stores/chat'
import ChatContainer from '../chat/ChatContainer.vue'
import WorkspaceViewer from './WorkspaceViewer.vue'
import { getOrCreateSessionId } from '../../lib/session'

const store = useArtifactsStore()
const chat = useChatStore()

const rightWidthPct = ref<number>(Number(localStorage.getItem('navibot_right_panel_pct') || '30'))
const dragging = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const stacked = ref(false)
const isStacked = computed(() => stacked.value)

function updateStacked() {
  stacked.value = window.matchMedia('(max-width: 900px)').matches
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function persist() {
  localStorage.setItem('navibot_right_panel_pct', String(rightWidthPct.value))
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value || !rootRef.value) return
  const rect = rootRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const pctRight = ((rect.width - x) / rect.width) * 100
  rightWidthPct.value = clamp(pctRight, 20, 60)
  persist()
}

function stopDrag() {
  dragging.value = false
}

function startDrag(e: PointerEvent) {
  if (isStacked.value) return
  dragging.value = true
  ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
}

onMounted(() => {
  updateStacked()
  window.addEventListener('resize', updateStacked)
  const sid = getOrCreateSessionId()
  store.setSessionId(sid)
  store.fetchArtifacts()
  store.connectSse()
  chat.loadSessionHistory(sid)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateStacked)
  store.disconnectSse()
})

const gridStyle = computed(() => {
  const right = clamp(rightWidthPct.value, 20, 60)
  const left = 100 - right
  return {
    gridTemplateColumns: `${left}% 8px ${right}%`
  }
})
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 overflow-hidden">
    <header class="p-4 bg-white border-b border-slate-200 flex justify-between items-center shadow-sm z-10">
      <div class="flex items-center gap-3">
        <div class="bg-sky-500 p-2 rounded-lg text-white">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </div>
        <h1 class="text-xl font-bold tracking-tight">Navibot <span class="text-sky-500 font-medium font-mono text-sm border border-sky-100 bg-sky-50 px-2 py-0.5 rounded ml-1">v2.0</span></h1>
      </div>
      <div class="flex items-center gap-3">
        <div v-if="store.unreadCount" class="text-xs bg-amber-100 text-amber-900 border border-amber-200 px-2 py-1 rounded-full">
          {{ store.unreadCount }} nuevo(s)
        </div>
        <div class="text-xs text-slate-500 font-mono">
          {{ store.sessionId }}
        </div>
      </div>
    </header>

    <main ref="rootRef" class="flex-1 min-h-0">
      <div class="pointer-events-none fixed top-16 right-4 z-50 flex flex-col gap-2">
        <div
          v-for="t in store.toasts.slice(-4)"
          :key="t.id"
          class="pointer-events-auto bg-slate-900 text-white text-sm px-3 py-2 rounded shadow-lg border border-slate-700"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="truncate max-w-[280px]">{{ t.message }}</div>
            <button
              class="text-slate-300 hover:text-white text-xs"
              type="button"
              @click="store.popToast(t.id)"
              aria-label="Cerrar notificación"
            >
              ✕
            </button>
          </div>
        </div>
      </div>

      <div v-if="isStacked" class="h-full flex flex-col">
        <div class="flex-1 min-h-0">
          <ChatContainer />
        </div>
        <div class="h-[40%] min-h-[260px] border-t border-slate-200">
          <WorkspaceViewer />
        </div>
      </div>

      <div
        v-else
        class="h-full grid"
        :style="gridStyle"
        @pointermove="onPointerMove"
        @pointerup="stopDrag"
        @pointercancel="stopDrag"
        @pointerleave="stopDrag"
      >
        <div class="min-w-0 min-h-0">
          <ChatContainer />
        </div>

        <div
          class="min-h-0 cursor-col-resize bg-slate-100 hover:bg-slate-200 transition-colors flex items-center justify-center"
          role="separator"
          aria-orientation="vertical"
          tabindex="0"
          @pointerdown="startDrag"
        >
          <div class="w-1 h-12 rounded bg-slate-300" />
        </div>

        <div class="min-w-0 min-h-0 border-l border-slate-200 bg-white">
          <WorkspaceViewer />
        </div>
      </div>
    </main>
  </div>
</template>
