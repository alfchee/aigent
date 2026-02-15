<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useArtifactsStore } from '../../stores/artifacts'
import { useSessionsStore } from '../../stores/sessions'
import FilePreview from './FilePreview.vue'
import { isCollapsed as isCollapsedState, nextSidebarState, sidebarWidthPx, type SidebarState } from '../../lib/sidebars'

const store = useArtifactsStore()
const sessions = useSessionsStore()

const props = defineProps<{
  sidebarState: SidebarState
  panelCollapsed: boolean
}>()

const emit = defineEmits<{
  (e: 'update:sidebarState', state: SidebarState): void
  (e: 'update:panelCollapsed', state: boolean): void
}>()

const selected = computed(() => store.selectedPath)
const selectedMeta = computed(() =>
  showTrash.value ? null : store.files.find((f) => f.path === store.selectedPath) || null
)
const collapsed = computed(() => isCollapsedState(props.sidebarState))
const sidebarWidth = computed(() => sidebarWidthPx(props.sidebarState))
const nextStateLabel = computed(() => nextSidebarState(props.sidebarState))

const uploading = ref(false)
const uploadError = ref<string | null>(null)
const actionError = ref<string | null>(null)
const search = ref('')
const showArchived = ref(false)
const archiveSessionId = ref('')
const showTrash = ref(false)
const showAudit = ref(false)

const isViewingArchive = computed(() => showArchived.value && Boolean(archiveSessionId.value))
const viewLabel = computed(() => (isViewingArchive.value ? 'Archivada' : 'Actual'))
const viewBadgeClass = computed(() =>
  isViewingArchive.value ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
)
const filteredFiles = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.files
  return store.files.filter((f) => f.path.toLowerCase().includes(q))
})
const filteredTrash = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return store.trash
  return store.trash.filter((f) => f.path.toLowerCase().includes(q))
})
const displayCount = computed(() => (showTrash.value ? filteredTrash.value.length : filteredFiles.value.length))

watch(
  () => showArchived.value,
  async (next) => {
    if (next) {
      await sessions.fetchSessions({ includeArchived: true })
      archiveSessionId.value = sessions.archivedSessions[0]?.id || ''
      await store.setViewSession(archiveSessionId.value || store.sessionId, Boolean(archiveSessionId.value))
      if (showTrash.value) await store.fetchTrash()
    } else {
      archiveSessionId.value = ''
      await store.setViewSession(store.sessionId, false)
      if (showTrash.value) await store.fetchTrash()
    }
  },
  { immediate: true }
)

watch(
  () => archiveSessionId.value,
  async (next) => {
    if (!showArchived.value) return
    await store.setViewSession(next || store.sessionId, Boolean(next))
    if (showTrash.value) await store.fetchTrash()
  }
)

watch(
  () => showTrash.value,
  async (next) => {
    if (next) {
      await store.fetchTrash()
      store.selectArtifact('')
    }
  }
)

watch(
  () => store.sessionId,
  async (next) => {
    if (showArchived.value) return
    await store.setViewSession(next, false)
    if (showTrash.value) await store.fetchTrash()
  }
)

async function refresh() {
  await store.fetchArtifacts()
}

async function uploadFile(file: File) {
  uploading.value = true
  uploadError.value = null
  actionError.value = null
  try {
    const form = new FormData()
    form.append('session_id', store.sessionId)
    form.append('file', file, file.name)
    const res = await fetch('/api/upload', { method: 'POST', body: form })
    if (!res.ok) throw new Error('Upload failed')
    await store.fetchArtifacts()
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : String(e)
  } finally {
    uploading.value = false
  }
}

function onPickFile(evt: Event) {
  const input = evt.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadFile(file)
  input.value = ''
}

async function toggleAudit() {
  showAudit.value = !showAudit.value
  if (showAudit.value) {
    await store.fetchAudit(20)
  }
}

async function confirmDelete(path: string) {
  actionError.value = null
  const ok = confirm(
    `¿Eliminar ${path} del workspace? Se moverá a la papelera y podrás restaurarlo por un tiempo limitado.`
  )
  if (!ok) return
  try {
    const result = await store.deleteArtifact(path, 'manual')
    const freed = store.formatBytes(result.freed_bytes || 0)
    const until = result.restore_until ? new Date(result.restore_until).toLocaleString() : ''
    const msg = until ? `Eliminado · ${freed} · Restaurable hasta ${until}` : `Eliminado · ${freed}`
    store.toasts.push({ id: `${Date.now()}_${Math.random()}`, message: msg })
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : String(e)
  }
}

async function confirmRestore(trashId: string) {
  actionError.value = null
  const ok = confirm('¿Restaurar este artefacto a su ubicación original?')
  if (!ok) return
  try {
    await store.restoreArtifact(trashId)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : String(e)
  }
}

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  const kb = n / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(1)} MB`
}

function toggleSidebar() {
  emit('update:sidebarState', nextSidebarState(props.sidebarState))
}

function togglePanel() {
  emit('update:panelCollapsed', !props.panelCollapsed)
}

function getIcon(mime: string | null | undefined, path: string) {
  if (path.endsWith('.csv')) return { name: 'table_chart', color: 'text-green-500' }
  if (path.endsWith('.json')) return { name: 'code', color: 'text-yellow-500' }
  if (path.endsWith('.html')) return { name: 'html', color: 'text-orange-500' }
  if (path.endsWith('.txt')) return { name: 'description', color: 'text-slate-400' }
  if (path.endsWith('.png') || path.endsWith('.jpg')) return { name: 'image', color: 'text-purple-500' }
  if (mime?.includes('image')) return { name: 'image', color: 'text-purple-500' }
  if (mime?.includes('csv')) return { name: 'table_chart', color: 'text-green-500' }
  if (mime?.includes('json')) return { name: 'code', color: 'text-yellow-500' }
  return { name: 'description', color: 'text-slate-400' }
}
</script>

<template>
  <div class="h-full min-h-0 flex flex-col bg-white">
    <div class="p-4 border-b border-slate-200 bg-gray-50/50">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-bold text-slate-800" :title="collapsed ? 'Artefactos' : ''">
            {{ collapsed ? 'Art.' : 'Artefactos' }}
          </span>
          <span v-if="!collapsed" class="bg-gray-100 text-slate-600 text-[10px] font-bold px-2 py-0.5 rounded-full">
            {{ displayCount }}
          </span>
          <span v-if="!collapsed" class="text-[10px] font-semibold px-2 py-0.5 rounded-full" :class="viewBadgeClass">
            {{ viewLabel }}
          </span>
        </div>
        <div class="flex items-center gap-1">
          <button
            class="p-1 text-slate-400 hover:text-sky-500 hover:bg-gray-100 rounded transition-colors"
            type="button"
            :title="`Cambiar tamaño: ${nextStateLabel}`"
            @click="toggleSidebar"
          >
            <span class="material-icons-outlined text-lg">view_sidebar</span>
          </button>
          <button
            class="p-1 text-slate-400 hover:text-sky-500 hover:bg-gray-100 rounded transition-colors"
            type="button"
            title="Colapsar panel"
            @click="togglePanel"
          >
            <span class="material-icons-outlined text-lg">chevron_right</span>
          </button>
        </div>
      </div>
      <div v-if="!collapsed" class="flex gap-2">
        <label
          v-if="!isViewingArchive"
          class="flex-1 flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-slate-200 rounded hover:bg-gray-50 text-slate-600 transition-colors cursor-pointer"
        >
          <input type="file" class="hidden" :disabled="uploading" @change="onPickFile" />
          <span class="material-icons-outlined text-sm">upload_file</span>
          {{ uploading ? 'Subiendo…' : 'Subir' }}
        </label>
        <button
          class="flex-1 flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-slate-200 rounded hover:bg-gray-50 text-slate-600 transition-colors"
          type="button"
          @click="refresh"
        >
          <span class="material-icons-outlined text-sm">refresh</span>
          Refrescar
        </button>
      </div>
      <div v-if="!collapsed" class="mt-2 flex gap-2">
        <input
          v-model="search"
          type="search"
          class="flex-1 text-xs px-3 py-1.5 border border-slate-200 rounded bg-white text-slate-700"
          :placeholder="showTrash ? 'Buscar en papelera' : 'Buscar en esta sesión'"
        />
        <button
          class="text-xs px-3 py-1.5 border rounded transition-colors"
          :class="showArchived ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-slate-200 bg-white text-slate-600'"
          type="button"
          @click="showArchived = !showArchived"
        >
          Archivadas
        </button>
        <button
          class="text-xs px-3 py-1.5 border rounded transition-colors"
          :class="showTrash ? 'border-rose-300 bg-rose-50 text-rose-700' : 'border-slate-200 bg-white text-slate-600'"
          type="button"
          @click="showTrash = !showTrash"
        >
          Papelera
        </button>
        <button
          class="text-xs px-3 py-1.5 border rounded transition-colors"
          :class="showAudit ? 'border-slate-300 bg-slate-100 text-slate-700' : 'border-slate-200 bg-white text-slate-600'"
          type="button"
          @click="toggleAudit"
        >
          Actividad
        </button>
      </div>
      <div v-if="!collapsed && showArchived" class="mt-2">
        <select
          v-model="archiveSessionId"
          class="w-full text-xs px-3 py-1.5 border border-slate-200 rounded bg-white text-slate-700"
        >
          <option value="">Selecciona sesión archivada</option>
          <option v-for="s in sessions.archivedSessions" :key="s.id" :value="s.id">
            {{ s.title || s.id }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="store.error" class="p-3 text-sm text-red-700 bg-red-50 border-b border-red-200">
      {{ store.error }}
    </div>
    <div v-if="uploadError" class="p-3 text-sm text-red-700 bg-red-50 border-b border-red-200">
      {{ uploadError }}
    </div>
    <div v-if="actionError" class="p-3 text-sm text-red-700 bg-red-50 border-b border-red-200">
      {{ actionError }}
    </div>

    <div class="flex-1 min-h-0 flex">
      <div
        data-testid="artifacts-sidebar"
        class="border-r border-slate-200 overflow-y-auto transition-all duration-300 custom-scrollbar"
        :style="{ width: sidebarWidth + 'px' }"
      >
        <div v-if="!store.loading && !showTrash && filteredFiles.length === 0" class="p-4 text-sm text-slate-500">
          {{ collapsed ? '—' : 'Aún no hay artefactos en esta sesión.' }}
        </div>
        <div v-if="!store.loading && showTrash && filteredTrash.length === 0" class="p-4 text-sm text-slate-500">
          {{ collapsed ? '—' : 'La papelera está vacía.' }}
        </div>
        <div
          v-for="f in filteredFiles"
          :key="f.path"
          class="border-b border-slate-200 p-3 hover:bg-gray-50 transition-colors cursor-pointer group"
          :class="f.path === selected ? 'bg-sky-50/50 border-l-4 border-l-sky-500' : 'bg-white'"
          :title="collapsed ? f.path : ''"
          @click="store.selectArtifact(f.path)"
          v-show="!showTrash"
        >
          <div class="flex justify-between items-start mb-1">
            <div class="flex items-center gap-2 overflow-hidden">
              <span class="material-icons-outlined text-lg" :class="getIcon(f.mime_type, f.path).color">
                {{ getIcon(f.mime_type, f.path).name }}
              </span>
              <span v-if="!collapsed" class="text-sm font-medium text-slate-700 truncate">{{ f.path }}</span>
            </div>
            <div v-if="!collapsed" class="flex items-center gap-1">
              <span class="text-[10px] text-slate-400 bg-gray-100 px-1.5 py-0.5 rounded truncate max-w-[60px]">{{
                f.mime_type || 'unknown'
              }}</span>
              <button
                class="text-[10px] px-1.5 py-0.5 rounded border border-rose-200 text-rose-600 hover:bg-rose-50"
                type="button"
                title="Eliminar"
                @click.stop="confirmDelete(f.path)"
              >
                Eliminar
              </button>
            </div>
          </div>
          <div v-if="!collapsed" class="text-[10px] text-slate-500 pl-7">
            {{ formatBytes(f.size_bytes) }} · {{ f.modified_at }}
          </div>
        </div>
        <div
          v-for="t in filteredTrash"
          :key="t.trash_id"
          class="border-b border-slate-200 p-3 bg-white"
          v-show="showTrash"
        >
          <div class="flex justify-between items-start mb-1">
            <div class="flex items-center gap-2 overflow-hidden">
              <span class="material-icons-outlined text-lg text-rose-500">delete</span>
              <span v-if="!collapsed" class="text-sm font-medium text-slate-700 truncate">{{ t.path }}</span>
            </div>
            <div v-if="!collapsed" class="flex items-center gap-1">
              <button
                class="text-[10px] px-1.5 py-0.5 rounded border border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                type="button"
                :disabled="t.expired"
                @click.stop="confirmRestore(t.trash_id)"
              >
                Restaurar
              </button>
            </div>
          </div>
          <div v-if="!collapsed" class="text-[10px] text-slate-500 pl-7">
            {{ formatBytes(t.size_bytes) }} · Eliminado {{ t.deleted_at }}
          </div>
          <div v-if="!collapsed" class="text-[10px] text-slate-400 pl-7">
            {{ t.expired ? 'Restauración expirada' : `Restaurable hasta ${t.restore_until}` }}
          </div>
        </div>
        <div v-if="showAudit && !collapsed" class="p-3 border-t border-slate-200 bg-gray-50/50">
          <div class="text-[11px] font-semibold text-slate-600 mb-2">Actividad reciente</div>
          <div v-if="store.audit.length === 0" class="text-[11px] text-slate-400">Sin registros</div>
          <div v-for="a in store.audit" :key="a.timestamp + (a.path || '')" class="text-[11px] text-slate-600">
            <span class="font-semibold">{{ a.op }}</span>
            <span v-if="a.path"> · {{ a.path }}</span>
            <span v-if="a.freed_bytes"> · {{ formatBytes(a.freed_bytes) }}</span>
          </div>
        </div>
      </div>

      <div class="min-w-0 flex-1 min-h-0 bg-white">
        <div v-if="showTrash" class="h-full flex items-center justify-center text-sm text-slate-500">
          Selecciona un artefacto en la papelera para restaurarlo.
        </div>
        <div v-else-if="!selected" class="h-full flex items-center justify-center text-sm text-slate-500">
          Selecciona un archivo para previsualizarlo.
        </div>
        <FilePreview
          v-else
          :session-id="store.viewSessionId"
          :allow-archived="store.viewAllowArchived"
          :file="selectedMeta!"
          @back="store.selectArtifact('')"
          @collapse="togglePanel"
        />
      </div>
    </div>
  </div>
</template>
