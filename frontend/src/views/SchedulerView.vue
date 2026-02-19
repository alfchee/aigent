<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import {
  useSchedulerStore,
  type SchedulerJob,
  type SchedulerTrigger,
} from '../stores/schedulerStore'

const store = useSchedulerStore()
const search = ref('')
const statusFilter = ref<'all' | 'active' | 'paused'>('all')
const selectedJobId = ref<string | null>(null)

const jobs = computed(() => store.jobs)
const logs = computed(() => store.logs)
const error = computed(() => store.error)
const jobsSectionLoading = computed(() => store.jobsSectionLoading)
const logsSectionLoading = computed(() => store.logsSectionLoading)
const isDev = (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV

// Virtual scrolling state avoids full re-rendering on each fetch.
const jobsContainer = ref<HTMLElement | null>(null)
const logsContainer = ref<HTMLElement | null>(null)
const jobsScrollTop = ref(0)
const logsScrollTop = ref(0)
const jobsViewportHeight = ref(360)
const logsViewportHeight = ref(360)
const jobRowHeight = 72
const logRowHeight = 64
const overscan = 6
const lastJobsRenderMs = ref<number | null>(null)
const lastLogsRenderMs = ref<number | null>(null)

const filteredJobs = computed(() => {
  const q = search.value.trim().toLowerCase()
  return jobs.value.filter((job) => {
    const matchesStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'paused' && job.paused) ||
      (statusFilter.value === 'active' && !job.paused)
    if (!matchesStatus) return false
    if (!q) return true
    return (
      job.name.toLowerCase().includes(q) ||
      job.id.toLowerCase().includes(q) ||
      job.prompt.toLowerCase().includes(q)
    )
  })
})

const jobsStartIndex = computed(() =>
  Math.max(0, Math.floor(jobsScrollTop.value / jobRowHeight) - overscan),
)
const jobsVisibleCount = computed(
  () => Math.ceil(jobsViewportHeight.value / jobRowHeight) + overscan * 2,
)
const visibleJobs = computed(() =>
  filteredJobs.value.slice(jobsStartIndex.value, jobsStartIndex.value + jobsVisibleCount.value),
)
const jobsTopPadding = computed(() => jobsStartIndex.value * jobRowHeight)
const jobsBottomPadding = computed(() => {
  const remaining = filteredJobs.value.length - (jobsStartIndex.value + jobsVisibleCount.value)
  return Math.max(0, remaining * jobRowHeight)
})

const logsStartIndex = computed(() =>
  Math.max(0, Math.floor(logsScrollTop.value / logRowHeight) - overscan),
)
const logsVisibleCount = computed(
  () => Math.ceil(logsViewportHeight.value / logRowHeight) + overscan * 2,
)
const visibleLogs = computed(() =>
  logs.value.slice(logsStartIndex.value, logsStartIndex.value + logsVisibleCount.value),
)
const logsTopPadding = computed(() => logsStartIndex.value * logRowHeight)
const logsBottomPadding = computed(() => {
  const remaining = logs.value.length - (logsStartIndex.value + logsVisibleCount.value)
  return Math.max(0, remaining * logRowHeight)
})

function formatTrigger(trigger: SchedulerTrigger) {
  if (trigger.type === 'date') {
    return `Única: ${trigger.run_date || 'sin fecha'}`
  }
  if (trigger.type === 'interval') {
    return `Cada ${trigger.seconds || 0}s`
  }
  if (trigger.type === 'cron') {
    const fields = trigger.fields || {}
    return `Cron: ${Object.values(fields).join(' ')}`
  }
  return trigger.repr || 'Desconocido'
}

function selectJob(job: SchedulerJob) {
  selectedJobId.value = job.id
  store.fetchLogs(job.id)
}

function clearSelection() {
  selectedJobId.value = null
  store.fetchLogs()
}

async function refreshAll() {
  await store.fetchJobs()
  await store.fetchLogs(selectedJobId.value || undefined)
}

async function pauseJob(job: SchedulerJob) {
  await store.pauseJob(job.id)
}

async function resumeJob(job: SchedulerJob) {
  await store.resumeJob(job.id)
}

async function deleteJob(job: SchedulerJob) {
  if (!confirm(`¿Eliminar el job ${job.name}?`)) return
  await store.deleteJob(job.id)
  if (selectedJobId.value === job.id) {
    selectedJobId.value = null
    await store.fetchLogs()
  }
}

let pollTimer: number | null = null
let resizeTimer: number | null = null

function updateViewports() {
  if (jobsContainer.value) jobsViewportHeight.value = jobsContainer.value.clientHeight
  if (logsContainer.value) logsViewportHeight.value = logsContainer.value.clientHeight
}

function onJobsScroll() {
  jobsScrollTop.value = jobsContainer.value?.scrollTop || 0
}

function onLogsScroll() {
  logsScrollTop.value = logsContainer.value?.scrollTop || 0
}

watch(
  () => store.jobs,
  async () => {
    const start = performance.now()
    await nextTick()
    updateViewports()
    const durationMs = performance.now() - start
    const improvementPct =
      lastJobsRenderMs.value !== null
        ? ((lastJobsRenderMs.value - durationMs) / lastJobsRenderMs.value) * 100
        : null
    if (isDev) {
      console.debug('[scheduler] jobs render update', {
        durationMs: Number(durationMs.toFixed(2)),
        improvementPct: improvementPct !== null ? Number(improvementPct.toFixed(2)) : null,
      })
    }
    lastJobsRenderMs.value = durationMs
  },
  { deep: true },
)

watch(
  () => store.logs,
  async () => {
    const start = performance.now()
    await nextTick()
    updateViewports()
    const durationMs = performance.now() - start
    const improvementPct =
      lastLogsRenderMs.value !== null
        ? ((lastLogsRenderMs.value - durationMs) / lastLogsRenderMs.value) * 100
        : null
    if (isDev) {
      console.debug('[scheduler] logs render update', {
        durationMs: Number(durationMs.toFixed(2)),
        improvementPct: improvementPct !== null ? Number(improvementPct.toFixed(2)) : null,
      })
    }
    lastLogsRenderMs.value = durationMs
  },
  { deep: true },
)

onMounted(async () => {
  await refreshAll()
  await nextTick()
  updateViewports()
  pollTimer = window.setInterval(() => {
    refreshAll()
  }, 5000)
  resizeTimer = window.setInterval(updateViewports, 1000)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (resizeTimer) window.clearInterval(resizeTimer)
})
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
    <header
      class="p-4 bg-white border-b border-slate-200 flex items-center justify-between shadow-sm sticky top-0 z-10"
    >
      <div class="flex items-center gap-3">
        <RouterLink
          to="/"
          class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50"
        >
          Volver
        </RouterLink>
        <RouterLink
          to="/settings"
          class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50"
        >
          Configuración
        </RouterLink>
        <div class="text-sm font-semibold text-slate-800">Scheduler Dashboard</div>
      </div>
      <button
        type="button"
        class="text-xs px-4 py-2 rounded bg-sky-600 text-white hover:bg-sky-700 font-medium transition-colors"
        @click="refreshAll"
      >
        Actualizar
      </button>
    </header>

    <main class="flex-1 p-4 md:p-8 max-w-6xl mx-auto w-full space-y-6">
      <div
        v-show="error"
        class="text-sm text-red-600 border border-red-200 bg-red-50 rounded-xl p-4"
      >
        {{ error }}
      </div>

      <section class="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-4">
        <div class="flex flex-col md:flex-row md:items-center gap-3">
          <input
            v-model="search"
            type="text"
            placeholder="Buscar por nombre, id o prompt"
            class="w-full md:w-1/2 p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm"
          />
          <select
            v-model="statusFilter"
            class="w-full md:w-48 p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm"
          >
            <option value="all">Todos</option>
            <option value="active">Activos</option>
            <option value="paused">Pausados</option>
          </select>
          <div class="text-xs text-slate-500">{{ filteredJobs.length }} job(s)</div>
        </div>

        <div v-show="jobsSectionLoading" class="space-y-2">
          <div class="h-6 bg-slate-100 rounded animate-pulse"></div>
          <div class="h-6 bg-slate-100 rounded animate-pulse"></div>
          <div class="h-6 bg-slate-100 rounded animate-pulse"></div>
        </div>

        <transition name="fade">
          <div
            v-show="!jobsSectionLoading"
            ref="jobsContainer"
            class="overflow-auto border border-slate-200 rounded-lg h-[420px]"
            @scroll="onJobsScroll"
          >
            <table class="min-w-full text-xs text-slate-700">
              <thead class="bg-slate-100 text-slate-700 uppercase tracking-wider">
                <tr>
                  <th class="text-left px-3 py-2">Job</th>
                  <th class="text-left px-3 py-2">Periodicidad</th>
                  <th class="text-left px-3 py-2">Próxima</th>
                  <th class="text-left px-3 py-2">Última</th>
                  <th class="text-left px-3 py-2">Estado</th>
                  <th class="text-left px-3 py-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr v-show="jobsTopPadding > 0" aria-hidden="true">
                  <td :style="{ height: `${jobsTopPadding}px` }" colspan="6"></td>
                </tr>
                <tr
                  v-for="job in visibleJobs"
                  :key="job.id"
                  class="odd:bg-white even:bg-slate-50 hover:bg-slate-100 cursor-pointer"
                  @click="selectJob(job)"
                >
                  <td class="px-3 py-2">
                    <div class="font-semibold text-slate-900">{{ job.name }}</div>
                    <div class="text-[10px] text-slate-500 break-all">{{ job.id }}</div>
                    <div class="text-[10px] text-slate-500">{{ job.session_id }}</div>
                  </td>
                  <td class="px-3 py-2">{{ formatTrigger(job.trigger) }}</td>
                  <td class="px-3 py-2 text-[11px]">{{ job.next_run_time || '—' }}</td>
                  <td class="px-3 py-2 text-[11px]">{{ job.last_run_time || '—' }}</td>
                  <td class="px-3 py-2">
                    <span
                      class="text-[10px] font-semibold px-2 py-1 rounded"
                      :class="
                        job.paused
                          ? 'bg-slate-200 text-slate-600'
                          : 'bg-emerald-100 text-emerald-700'
                      "
                    >
                      {{ job.paused ? 'PAUSADO' : 'ACTIVO' }}
                    </span>
                  </td>
                  <td class="px-3 py-2">
                    <div class="flex items-center gap-2">
                      <button
                        v-if="!job.paused"
                        class="text-xs px-2 py-1 rounded bg-slate-200 hover:bg-slate-300"
                        @click.stop="pauseJob(job)"
                      >
                        Pausar
                      </button>
                      <button
                        v-else
                        class="text-xs px-2 py-1 rounded bg-emerald-100 hover:bg-emerald-200 text-emerald-800"
                        @click.stop="resumeJob(job)"
                      >
                        Reanudar
                      </button>
                      <button
                        class="text-xs px-2 py-1 rounded bg-rose-100 hover:bg-rose-200 text-rose-700"
                        @click.stop="deleteJob(job)"
                      >
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-show="jobsBottomPadding > 0" aria-hidden="true">
                  <td :style="{ height: `${jobsBottomPadding}px` }" colspan="6"></td>
                </tr>
                <tr v-show="filteredJobs.length === 0">
                  <td colspan="6" class="px-3 py-6 text-center text-slate-500 text-sm">
                    No hay jobs programados
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </transition>
      </section>

      <section class="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-4">
        <div class="flex items-center justify-between">
          <div class="text-sm font-semibold text-slate-800">
            Logs de ejecución
            <span v-if="selectedJobId" class="text-xs text-slate-500">· {{ selectedJobId }}</span>
          </div>
          <button
            v-if="selectedJobId"
            class="text-xs px-3 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50"
            @click="clearSelection"
          >
            Ver todos
          </button>
        </div>

        <div v-show="logsSectionLoading" class="space-y-2">
          <div class="h-6 bg-slate-100 rounded animate-pulse"></div>
          <div class="h-6 bg-slate-100 rounded animate-pulse"></div>
          <div class="h-6 bg-slate-100 rounded animate-pulse"></div>
        </div>

        <transition name="fade">
          <div
            v-show="!logsSectionLoading"
            ref="logsContainer"
            class="overflow-auto border border-slate-200 rounded-lg h-[420px]"
            @scroll="onLogsScroll"
          >
            <table class="min-w-full text-xs text-slate-700">
              <thead class="bg-slate-100 text-slate-700 uppercase tracking-wider">
                <tr>
                  <th class="text-left px-3 py-2">Estado</th>
                  <th class="text-left px-3 py-2">Inicio</th>
                  <th class="text-left px-3 py-2">Duración</th>
                  <th class="text-left px-3 py-2">Resultado</th>
                </tr>
              </thead>
              <tbody>
                <tr v-show="logsTopPadding > 0" aria-hidden="true">
                  <td :style="{ height: `${logsTopPadding}px` }" colspan="4"></td>
                </tr>
                <tr
                  v-for="log in visibleLogs"
                  :key="`${log.started_at}-${log.job_id}`"
                  class="odd:bg-white even:bg-slate-50"
                >
                  <td class="px-3 py-2">
                    <span
                      class="text-[10px] font-semibold px-2 py-1 rounded"
                      :class="
                        log.status === 'success'
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-rose-100 text-rose-700'
                      "
                    >
                      {{ log.status }}
                    </span>
                  </td>
                  <td class="px-3 py-2 text-[11px]">{{ log.started_at }}</td>
                  <td class="px-3 py-2 text-[11px]">{{ log.duration_seconds }}s</td>
                  <td class="px-3 py-2 text-[11px]">
                    <div class="font-medium text-slate-800 line-clamp-2">
                      {{ log.response || log.error }}
                    </div>
                    <div class="text-[10px] text-slate-500">{{ log.prompt }}</div>
                  </td>
                </tr>
                <tr v-show="logsBottomPadding > 0" aria-hidden="true">
                  <td :style="{ height: `${logsBottomPadding}px` }" colspan="4"></td>
                </tr>
                <tr v-show="logs.length === 0">
                  <td colspan="4" class="px-3 py-6 text-center text-slate-500 text-sm">
                    No hay ejecuciones registradas
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </transition>
      </section>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
