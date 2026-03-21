<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ChevronDown, ChevronUp, Activity } from 'lucide-vue-next'
import { useWebSocketStore } from '@/stores/websocket'
import { useUserConfigStore } from '@/stores/userConfig'
import WorkerStatusBar from './WorkerStatusBar.vue'
import PendingTasksBadge from './PendingTasksBadge.vue'

const props = withDefaults(
  defineProps<{
    sessionId?: string
    autoRefreshInterval?: number
  }>(),
  { autoRefreshInterval: 30000, sessionId: undefined },
)

const wsStore = useWebSocketStore()
const userStore = useUserConfigStore()

const collapsed = ref(false)
const expandedTasks = ref(false)
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | null = null

const sessionId = computed(() => props.sessionId ?? userStore.sessionId)
const state = computed(() => wsStore.getAgentState(sessionId.value))

const hasState = computed(() => state.value !== null)

const lastActivityRelative = computed(() => {
  if (!state.value?.last_activity) return '—'
  const then = new Date(state.value.last_activity).getTime()
  const diff = Math.floor((now.value - then) / 1000)
  if (diff < 60) return `hace ${diff}s`
  const min = Math.floor(diff / 60)
  if (min < 60) return `hace ${min}min`
  const hr = Math.floor(min / 60)
  return `hace ${hr}h`
})

const workersArray = computed(() => {
  if (!state.value?.workers) return []
  return Object.values(state.value.workers)
})

function toggle() {
  collapsed.value = !collapsed.value
}

onMounted(() => {
  ticker = setInterval(() => {
    now.value = Date.now()
  }, 10000)
})

onUnmounted(() => {
  if (ticker) clearInterval(ticker)
})

defineExpose({ toggle })
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-semibold text-text flex items-center gap-2">
        📊 Estado de Sesión
      </h3>
      <button
        type="button"
        class="flex items-center gap-1 text-xs text-muted hover:text-text transition-colors"
        @click="toggle"
      >
        {{ collapsed ? 'Expandir' : 'Colapsar' }}
        <component :is="collapsed ? ChevronDown : ChevronUp" class="h-3.5 w-3.5" />
      </button>
    </div>

    <div v-if="!hasState" class="flex items-center justify-center py-6">
      <div class="flex flex-col items-center gap-2 text-muted">
        <Activity class="h-6 w-6 opacity-40" />
        <p class="text-xs">Sin datos de sesión disponibles</p>
        <p class="text-[11px] opacity-70">Envía un mensaje para ver el estado</p>
      </div>
    </div>

    <div v-else-if="!collapsed" class="flex flex-col gap-3">
      <div class="grid grid-cols-3 gap-2 text-center">
        <div class="rounded-lg border border-border bg-surface2/30 p-2">
          <div class="text-[11px] text-muted">Turns</div>
          <div class="text-sm font-semibold tabular-nums">{{ state!.total_turns }}</div>
        </div>
        <div class="rounded-lg border border-border bg-surface2/30 p-2">
          <div class="text-[11px] text-muted">Errors</div>
          <div
            class="text-sm font-semibold tabular-nums"
            :class="state!.total_errors > 0 ? 'text-danger' : 'text-muted'"
          >
            {{ state!.total_errors }}
          </div>
        </div>
        <div class="rounded-lg border border-border bg-surface2/30 p-2">
          <div class="text-[11px] text-muted">Activo</div>
          <div class="text-xs font-medium truncate">
            {{ state!.active_worker ?? '—' }}
          </div>
        </div>
      </div>

      <div
        v-if="state!.last_tool_used"
        class="rounded-lg border border-border p-2 text-xs"
      >
        <span class="text-muted">Último tool: </span>
        <span class="font-medium">{{ state!.last_tool_used }}</span>
        <span class="text-muted ml-2">{{ lastActivityRelative }}</span>
      </div>

      <div v-if="workersArray.length > 0" class="rounded-lg border border-border p-3">
        <div class="text-[11px] text-muted font-medium uppercase tracking-wide mb-2">
          Workers
        </div>
        <div class="flex flex-col gap-1.5">
          <WorkerStatusBar
            v-for="worker in workersArray"
            :key="worker.role_id"
            :worker="worker"
            :show-details="true"
          />
        </div>
      </div>

      <PendingTasksBadge
        :tasks="state!.pending_tasks"
        :expanded="expandedTasks"
        @toggle="expandedTasks = !expandedTasks"
      />
    </div>

    <div v-else class="text-xs text-muted text-center py-2">
      Turns: {{ state?.total_turns ?? 0 }} · Errors: {{ state?.total_errors ?? 0 }}
    </div>
  </div>
</template>
