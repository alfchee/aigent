<script setup lang="ts">
import { computed, ref } from 'vue'

import { useArtifactsStore } from '../../stores/artifacts'
import FilePreview from './FilePreview.vue'

const store = useArtifactsStore()

const selected = computed(() => store.selectedPath)
const selectedMeta = computed(() => store.files.find((f) => f.path === store.selectedPath) || null)

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
</script>

<template>
  <div class="h-full min-h-0 flex flex-col">
    <div class="p-3 border-b border-slate-200 flex items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <div class="text-sm font-semibold">Artefactos</div>
        <div v-if="store.loading" class="text-xs text-slate-500">Cargando…</div>
        <div v-else class="text-xs text-slate-500">{{ store.files.length }} archivo(s)</div>
      </div>
      <div class="flex items-center gap-2">
        <label class="text-xs px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 cursor-pointer">
          <input type="file" class="hidden" :disabled="uploading" @change="onPickFile" />
          {{ uploading ? 'Subiendo…' : 'Subir' }}
        </label>
        <button
          class="text-xs px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50"
          type="button"
          @click="refresh"
        >
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

    <div class="flex-1 min-h-0 grid grid-rows-[auto_1fr]">
      <div class="border-b border-slate-200 overflow-y-auto max-h-[240px]">
        <div v-if="!store.loading && store.files.length === 0" class="p-4 text-sm text-slate-500">
          Aún no hay artefactos en esta sesión.
        </div>
        <button
          v-for="f in store.files"
          :key="f.path"
          class="w-full text-left px-3 py-2 hover:bg-slate-50 border-b border-slate-100 flex items-center justify-between gap-2"
          :class="f.path === selected ? 'bg-sky-50' : 'bg-white'"
          type="button"
          @click="store.selectArtifact(f.path)"
        >
          <div class="min-w-0">
            <div class="text-sm font-medium truncate">{{ f.path }}</div>
            <div class="text-xs text-slate-500 truncate">{{ formatBytes(f.size_bytes) }} · {{ f.modified_at }}</div>
          </div>
          <div class="text-[10px] text-slate-400 font-mono">{{ f.mime_type || '' }}</div>
        </button>
      </div>

      <div class="min-h-0">
        <div v-if="!selected" class="h-full flex items-center justify-center text-sm text-slate-500">
          Selecciona un archivo para previsualizarlo.
        </div>
        <FilePreview v-else :session-id="store.sessionId" :file="selectedMeta!" />
      </div>
    </div>
  </div>
</template>
