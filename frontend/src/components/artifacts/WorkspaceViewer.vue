<script setup lang="ts">
import { computed, ref } from 'vue'

import { useArtifactsStore } from '../../stores/artifacts'
import FilePreview from './FilePreview.vue'
import { isCollapsed as isCollapsedState, nextSidebarState, sidebarWidthPx, type SidebarState } from '../../lib/sidebars'

const store = useArtifactsStore()

const props = defineProps<{
  sidebarState: SidebarState
  panelCollapsed: boolean
}>()

const emit = defineEmits<{
  (e: 'update:sidebarState', state: SidebarState): void
  (e: 'update:panelCollapsed', state: boolean): void
}>()

const selected = computed(() => store.selectedPath)
const selectedMeta = computed(() => store.files.find((f) => f.path === store.selectedPath) || null)
const collapsed = computed(() => isCollapsedState(props.sidebarState))
const sidebarWidth = computed(() => sidebarWidthPx(props.sidebarState))
const nextStateLabel = computed(() => nextSidebarState(props.sidebarState))

const uploading = ref(false)
const uploadError = ref<string | null>(null)

async function refresh() {
  await store.fetchArtifacts()
}

async function uploadFile(file: File) {
  uploading.value = true
  uploadError.value = null
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
            {{ store.files.length }}
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
        <label class="flex-1 flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-slate-200 rounded hover:bg-gray-50 text-slate-600 transition-colors cursor-pointer">
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
    </div>

    <div v-if="store.error" class="p-3 text-sm text-red-700 bg-red-50 border-b border-red-200">
      {{ store.error }}
    </div>
    <div v-if="uploadError" class="p-3 text-sm text-red-700 bg-red-50 border-b border-red-200">
      {{ uploadError }}
    </div>

    <div class="flex-1 min-h-0 flex">
      <div
        data-testid="artifacts-sidebar"
        class="border-r border-slate-200 overflow-y-auto transition-all duration-300 custom-scrollbar"
        :style="{ width: sidebarWidth + 'px' }"
      >
        <div v-if="!store.loading && store.files.length === 0" class="p-4 text-sm text-slate-500">
          {{ collapsed ? '—' : 'Aún no hay artefactos en esta sesión.' }}
        </div>
        <div
          v-for="f in store.files"
          :key="f.path"
          class="border-b border-slate-200 p-3 hover:bg-gray-50 transition-colors cursor-pointer group"
          :class="f.path === selected ? 'bg-sky-50/50 border-l-4 border-l-sky-500' : 'bg-white'"
          :title="collapsed ? f.path : ''"
          @click="store.selectArtifact(f.path)"
        >
          <div class="flex justify-between items-start mb-1">
            <div class="flex items-center gap-2 overflow-hidden">
              <span class="material-icons-outlined text-lg" :class="getIcon(f.mime_type, f.path).color">
                {{ getIcon(f.mime_type, f.path).name }}
              </span>
              <span v-if="!collapsed" class="text-sm font-medium text-slate-700 truncate">{{ f.path }}</span>
            </div>
            <span v-if="!collapsed" class="text-[10px] text-slate-400 bg-gray-100 px-1.5 py-0.5 rounded truncate max-w-[60px]">{{ f.mime_type || 'unknown' }}</span>
          </div>
          <div v-if="!collapsed" class="text-[10px] text-slate-500 pl-7">
            {{ formatBytes(f.size_bytes) }} · {{ f.modified_at }}
          </div>
        </div>
      </div>

      <div class="min-w-0 flex-1 min-h-0 bg-white">
        <div v-if="!selected" class="h-full flex items-center justify-center text-sm text-slate-500">
          Selecciona un archivo para previsualizarlo.
        </div>
        <FilePreview v-else :session-id="store.sessionId" :file="selectedMeta!" @back="store.selectArtifact('')" @collapse="togglePanel" />
      </div>
    </div>
  </div>
</template>
