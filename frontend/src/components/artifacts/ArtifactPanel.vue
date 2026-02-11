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
const artifactsPanelCollapsed = ref<boolean>(localStorage.getItem('navibot_artifacts_panel_collapsed') === 'true')

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

function persistPanel() {
  localStorage.setItem('navibot_artifacts_panel_collapsed', String(artifactsPanelCollapsed.value))
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

function setArtifactsPanelCollapsed(next: boolean) {
  artifactsPanelCollapsed.value = next
  persistPanel()
}

const gridStyle = computed(() => {
  if (artifactsPanelCollapsed.value) {
    return {
      gridTemplateColumns: `100% 8px 0%`
    }
  }
  const right = clamp(rightWidthPct.value, 20, 60)
  const left = 100 - right
  return {
    gridTemplateColumns: `${left}% 8px ${right}%`
  }
})
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 overflow-hidden">
    <header class="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 shrink-0 z-20 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="bg-sky-500 text-white p-1.5 rounded-lg">
          <span class="material-icons-outlined text-2xl">near_me</span>
        </div>
        <h1 class="text-xl font-bold tracking-tight text-slate-900">Navibot</h1>
        <span class="px-2 py-0.5 text-xs font-medium bg-sky-50 text-sky-500 rounded-full">v2.0</span>
      </div>
      <div class="flex items-center gap-3">
        <div class="hidden md:flex items-center gap-2">
          <div v-if="store.sessionId" class="flex items-center gap-2 text-sm text-slate-500 border border-slate-200 rounded-md px-3 py-1.5 bg-gray-50">
            <span class="material-icons-outlined text-xs">fingerprint</span>
            <span class="truncate font-mono text-xs max-w-[150px]">{{ store.sessionId }}</span>
          </div>
          <RouterLink
            to="/channels"
            class="flex items-center justify-center p-1.5 text-slate-500 hover:text-slate-700 border border-slate-200 rounded-md hover:bg-gray-100 transition-colors"
            title="Channels"
          >
            <span class="material-icons-outlined text-sm">hub</span>
          </RouterLink>
          <RouterLink
            to="/settings"
            class="flex items-center justify-center p-1.5 text-slate-500 hover:text-slate-700 border border-slate-200 rounded-md hover:bg-gray-100 transition-colors"
            title="Settings"
          >
            <span class="material-icons-outlined text-sm">settings</span>
          </RouterLink>
          <div v-if="store.unreadCount" class="text-xs bg-amber-100 text-amber-900 border border-amber-200 px-2 py-1 rounded-full">
            {{ store.unreadCount }} new
          </div>
        </div>
        <div class="h-6 w-px bg-slate-200 mx-1 hidden md:block"></div>
        <button class="p-2 rounded-full hover:bg-gray-100 transition-colors text-slate-500" id="theme-toggle" title="Toggle Theme (Not Implemented)">
          <span class="material-icons-outlined">dark_mode</span>
        </button>
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
        <div v-if="!artifactsPanelCollapsed" class="h-[40%] min-h-[260px] border-t border-slate-200">
          <WorkspaceViewer
            :sidebarState="artifactsSidebarState"
            :panelCollapsed="artifactsPanelCollapsed"
            @update:sidebarState="setArtifactsSidebarState"
            @update:panelCollapsed="setArtifactsPanelCollapsed"
          />
        </div>
        <div v-else class="h-12 border-t border-slate-200 flex items-center justify-center bg-white">
          <button
            class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-gray-50 border border-slate-200 rounded-md hover:bg-gray-100 transition-colors flex items-center gap-1.5"
            type="button"
            @click="setArtifactsPanelCollapsed(false)"
          >
            <span class="material-icons-outlined text-sm">chevron_left</span>
            Expandir Artefactos
          </button>
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
          class="min-h-0 cursor-col-resize bg-slate-100 hover:bg-slate-200 transition-colors flex items-center justify-center relative"
          role="separator"
          aria-orientation="vertical"
          tabindex="0"
          @pointerdown="startDrag"
        >
          <div class="w-1 h-12 rounded bg-slate-300" />
          <button
            v-if="artifactsPanelCollapsed"
            class="absolute right-1 top-1/2 -translate-y-1/2 p-1.5 bg-white border border-slate-200 rounded-full shadow text-slate-500 hover:text-slate-700 hover:bg-gray-50"
            type="button"
            title="Expandir panel"
            @click.stop="setArtifactsPanelCollapsed(false)"
          >
            <span class="material-icons-outlined text-lg">chevron_left</span>
          </button>
        </div>

        <div v-show="!artifactsPanelCollapsed" class="min-w-0 min-h-0 border-l border-slate-200 bg-white">
          <WorkspaceViewer
            :sidebarState="artifactsSidebarState"
            :panelCollapsed="artifactsPanelCollapsed"
            @update:sidebarState="setArtifactsSidebarState"
            @update:panelCollapsed="setArtifactsPanelCollapsed"
          />
        </div>
      </div>
    </main>
  </div>
</template>
