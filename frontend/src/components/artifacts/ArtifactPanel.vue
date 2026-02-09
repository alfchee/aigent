<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { useArtifactsStore } from '../../stores/artifacts'
import { useChatStore } from '../../stores/chat'
import { useSessionsStore } from '../../stores/sessions'
import ChatContainer from '../chat/ChatContainer.vue'
import Sidebar from '../chat/Sidebar.vue'
import WorkspaceViewer from './WorkspaceViewer.vue'
import { generateSessionId, getOrCreateSessionId, setSessionId } from '../../lib/session'
import { nextSidebarState, normalizeSidebarState, type SidebarState } from '../../lib/sidebars'

const store = useArtifactsStore()
const chat = useChatStore()
const sessions = useSessionsStore()

const sessionsSidebarState = ref<SidebarState>(
  normalizeSidebarState(localStorage.getItem('navibot_sidebar_sessions_state'), 'normal')
)
const artifactsSidebarState = ref<SidebarState>(
  normalizeSidebarState(localStorage.getItem('navibot_sidebar_artifacts_state'), 'normal')
)

if (sessionsSidebarState.value === 'collapsed' && artifactsSidebarState.value === 'collapsed') {
  artifactsSidebarState.value = 'normal'
  localStorage.setItem('navibot_sidebar_artifacts_state', artifactsSidebarState.value)
}

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

function persistSidebars() {
  localStorage.setItem('navibot_sidebar_sessions_state', sessionsSidebarState.value)
  localStorage.setItem('navibot_sidebar_artifacts_state', artifactsSidebarState.value)
}

function cannotCollapseBoth(target: 'sessions' | 'artifacts', next: SidebarState) {
  if (next !== 'collapsed') return false
  if (target === 'sessions' && artifactsSidebarState.value === 'collapsed') return true
  if (target === 'artifacts' && sessionsSidebarState.value === 'collapsed') return true
  return false
}

function notify(msg: string) {
  const toast = { id: `${Date.now()}_${Math.random()}`, message: msg }
  store.toasts.push(toast)
  window.setTimeout(() => store.popToast(toast.id), 3500)
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
  void setActiveSession(sid)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateStacked)
  store.disconnectSse()
})

async function setActiveSession(sid: string) {
  const sessionId = sid || 'default'
  setSessionId(sessionId)
  store.disconnectSse()
  store.setSessionId(sessionId)
  store.connectSse()
  try {
    await sessions.createSession(sessionId)
  } catch {
  }
  await Promise.allSettled([store.fetchArtifacts(), chat.loadSessionHistory(sessionId)])
}

async function createNewSession() {
  const sid = generateSessionId()
  try {
    await sessions.createSession(sid, 'Nueva Conversación')
  } catch {
  }
  await setActiveSession(sid)
}

async function deleteSession(sessionId: string) {
  try {
    await sessions.deleteSession(sessionId)
  } catch {
  }
  const remaining = sessions.sessions[0]?.id
  if (store.sessionId === sessionId) {
    await setActiveSession(remaining || generateSessionId())
  }
}

function toggleSessionsSidebar() {
  const next = nextSidebarState(sessionsSidebarState.value)
  if (cannotCollapseBoth('sessions', next)) {
    notify('No puedes colapsar Sesiones y Artefactos al mismo tiempo.')
    return
  }
  sessionsSidebarState.value = next
  persistSidebars()
}

function setArtifactsSidebarState(next: SidebarState) {
  if (cannotCollapseBoth('artifacts', next)) {
    notify('No puedes colapsar Sesiones y Artefactos al mismo tiempo.')
    return
  }
  artifactsSidebarState.value = next
  persistSidebars()
}

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
        <RouterLink
          to="/settings"
          class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50"
          title="Settings"
        >
          ⚙
        </RouterLink>
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
        <div class="h-[260px] min-h-[200px] border-b border-slate-200">
          <Sidebar
            :activeSessionId="store.sessionId"
            sidebarState="normal"
            @select="setActiveSession"
            @new="createNewSession"
            @delete="deleteSession"
            @toggle="toggleSessionsSidebar"
          />
        </div>
        <div class="flex-1 min-h-0">
          <ChatContainer />
        </div>
        <div class="h-[40%] min-h-[260px] border-t border-slate-200">
          <WorkspaceViewer
            :sidebarState="artifactsSidebarState"
            @update:sidebarState="setArtifactsSidebarState"
          />
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
          <div class="h-full flex">
            <Sidebar
              :activeSessionId="store.sessionId"
              :sidebarState="sessionsSidebarState"
              @select="setActiveSession"
              @new="createNewSession"
              @delete="deleteSession"
              @toggle="toggleSessionsSidebar"
            />
            <div class="flex-1 min-w-0">
              <ChatContainer />
            </div>
          </div>
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
          <WorkspaceViewer
            :sidebarState="artifactsSidebarState"
            @update:sidebarState="setArtifactsSidebarState"
          />
        </div>
      </div>
    </main>
  </div>
</template>
