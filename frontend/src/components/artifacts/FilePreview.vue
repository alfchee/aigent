<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import Papa from 'papaparse'

import { fetchBlob, fetchText } from '../../lib/api'
import SyntaxHighlighter from './SyntaxHighlighter.vue'
import HtmlRenderer from './HtmlRenderer.vue'
import type { ArtifactFileEntry } from '../../stores/artifacts'

const props = defineProps<{
  sessionId: string
  file: ArtifactFileEntry
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'collapse'): void
}>()

const loading = ref(false)
const error = ref<string | null>(null)

const text = ref<string | null>(null)
const rows = ref<Record<string, unknown>[]>([])
const columns = ref<string[]>([])
const query = ref('')
const page = ref(1)
const pageSize = ref(25)

const objectUrl = ref<string | null>(null)
const zoom = ref(1)
const copied = ref(false)
const copyTimer = ref<number | null>(null)

const path = computed(() => props.file.path)
const ext = computed(() => (props.file.path.split('.').pop() || '').toLowerCase())
const isLarge = computed(() => props.file.size_bytes > 10 * 1024 * 1024)
const sizeLabel = computed(() => {
  const n = props.file.size_bytes
  if (n < 1024) return `${n} B`
  const kb = n / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(1)} MB`
})

function encodePathSegments(p: string) {
  return p
    .split('/')
    .map((seg) => encodeURIComponent(seg))
    .join('/')
}

const downloadUrl = computed(() => {
  const base = `/api/files/${encodeURIComponent(props.sessionId)}/${encodePathSegments(props.file.path)}`
  return `${base}?download=true`
})

const viewUrl = computed(() => `/api/files/${encodeURIComponent(props.sessionId)}/${encodePathSegments(props.file.path)}`)

const isImage = computed(() => ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext.value))
const isHtml = computed(() => ['html', 'htm'].includes(ext.value))
const isPdf = computed(() => ext.value === 'pdf')
const isJson = computed(() => ext.value === 'json')
const isCsv = computed(() => ext.value === 'csv')
const isCode = computed(() => ['js', 'ts', 'tsx', 'vue', 'py', 'css', 'scss', 'html', 'htm', 'md', 'json', 'yml', 'yaml'].includes(ext.value))

const language = computed(() => {
  const map: Record<string, string> = {
    js: 'javascript',
    ts: 'typescript',
    tsx: 'tsx',
    vue: 'xml',
    py: 'python',
    css: 'css',
    scss: 'scss',
    html: 'xml',
    htm: 'xml',
    md: 'markdown',
    json: 'json',
    yml: 'yaml',
    yaml: 'yaml'
  }
  return map[ext.value] || 'plaintext'
})

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter((r) => JSON.stringify(r).toLowerCase().includes(q))
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)))
const paged = computed(() => {
  const p = Math.max(1, Math.min(page.value, totalPages.value))
  const start = (p - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})
const canCopy = computed(() => !!text.value)
const rawPreview = computed(() => {
  if (!text.value) return ''
  if (isJson.value) {
    try {
      return JSON.stringify(JSON.parse(text.value), null, 2)
    } catch {
      return text.value
    }
  }
  return text.value
})

function clearCopyState() {
  if (copyTimer.value) {
    window.clearTimeout(copyTimer.value)
    copyTimer.value = null
  }
}

async function copyRaw() {
  if (!text.value) return
  try {
    if (!navigator.clipboard?.writeText) return
    await navigator.clipboard.writeText(text.value)
    copied.value = true
    clearCopyState()
    copyTimer.value = window.setTimeout(() => {
      copied.value = false
      copyTimer.value = null
    }, 1500)
  } catch {
    copied.value = false
  }
}

function resetState() {
  loading.value = false
  error.value = null
  text.value = null
  rows.value = []
  columns.value = []
  query.value = ''
  page.value = 1
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = null
  }
  zoom.value = 1
  copied.value = false
  clearCopyState()
}

async function load() {
  resetState()
  if (isLarge.value) return

  loading.value = true
  error.value = null
  try {
    if (isImage.value) {
      const blob = await fetchBlob(viewUrl.value)
      objectUrl.value = URL.createObjectURL(blob)
      return
    }

    if (isPdf.value) {
      return
    }

    const content = await fetchText(viewUrl.value)
    text.value = content

    if (isJson.value) {
      const parsed = JSON.parse(content)
      if (Array.isArray(parsed)) {
        const normalized = parsed.slice(0, 500).map((v, idx) => (typeof v === 'object' && v ? v : { value: v, index: idx }))
        rows.value = normalized as any
        columns.value = Array.from(new Set(rows.value.flatMap((r) => Object.keys(r))))
      } else if (typeof parsed === 'object' && parsed) {
        rows.value = [parsed as any]
        columns.value = Object.keys(parsed as any)
      } else {
        rows.value = [{ value: parsed }]
        columns.value = ['value']
      }
    } else if (isCsv.value) {
      const result = Papa.parse<Record<string, unknown>>(content, { header: true, skipEmptyLines: true })
      const data = (result.data || []).slice(0, 500)
      rows.value = data
      columns.value = Array.from(new Set(data.flatMap((r: Record<string, unknown>) => Object.keys(r))))
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

watch(
  () => props.file.path,
  () => load(),
  { immediate: true }
)

onBeforeUnmount(() => {
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
  clearCopyState()
})
</script>

<template>
  <div class="h-full min-h-0 flex flex-col">
    <div class="p-4 border-b border-slate-200 flex items-center justify-between gap-2 bg-gray-50/50">
      <div class="flex items-center gap-2 min-w-0">
        <button
          class="flex items-center justify-center p-1.5 text-slate-500 hover:text-slate-800 rounded-md hover:bg-gray-200 transition-colors"
          type="button"
          title="Volver a la lista"
          @click="emit('back')"
        >
          <span class="material-icons-outlined text-sm">arrow_back</span>
        </button>
        <div class="min-w-0">
          <div class="text-sm font-bold text-slate-800 truncate">{{ path }}</div>
          <div class="text-[10px] text-slate-500">Preview Mode</div>
        </div>
      </div>
      <div class="flex items-center gap-1">
        <a
          class="p-1.5 text-slate-400 hover:text-sky-500 hover:bg-gray-100 rounded transition-colors"
          :href="viewUrl"
          title="Abrir archivo"
          aria-label="Abrir archivo"
        >
          <span class="material-icons-outlined text-lg">open_in_new</span>
        </a>
        <button
          class="p-1.5 text-slate-400 hover:text-sky-500 hover:bg-gray-100 rounded transition-colors"
          type="button"
          title="Colapsar panel"
          @click="emit('collapse')"
        >
          <span class="material-icons-outlined text-lg">chevron_right</span>
        </button>
      </div>
    </div>
    <div class="px-4 py-2 border-b border-slate-200 flex items-center gap-2 bg-white">
      <a
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-gray-50 border border-slate-200 rounded-md hover:bg-gray-100 transition-colors"
        :href="downloadUrl"
        aria-label="Descargar archivo"
      >
        <span class="material-icons-outlined text-sm">download</span>
        Download
      </a>
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-gray-50 border border-slate-200 rounded-md hover:bg-gray-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        type="button"
        :disabled="!canCopy"
        @click="copyRaw"
      >
        <span class="material-icons-outlined text-sm">content_copy</span>
        {{ copied ? 'Copiado' : 'Copy Raw' }}
      </button>
      <div class="flex-1"></div>
      <span class="text-[10px] text-slate-400 font-mono">{{ sizeLabel }}</span>
    </div>

    <div v-if="isLarge" class="p-4 text-sm text-slate-600">
      Este archivo supera 10MB. Para evitar degradación de rendimiento, se desactiva la previsualización completa.
    </div>

    <div v-else-if="loading" class="p-4 text-sm text-slate-500">Cargando preview…</div>
    <div v-else-if="error" class="p-4 text-sm text-red-700 bg-red-50 border border-red-200 m-3 rounded">
      {{ error }}
    </div>

    <div v-else class="flex-1 min-h-0 overflow-auto bg-gray-50">
      <div v-if="isImage && objectUrl" class="p-4">
        <div class="flex items-center justify-between mb-2">
          <div class="text-xs text-slate-500">Zoom</div>
          <input v-model.number="zoom" type="range" min="1" max="3" step="0.1" class="w-40" />
        </div>
        <div class="border border-slate-200 rounded bg-white p-2 overflow-auto">
          <img
            :src="objectUrl"
            :alt="path"
            class="max-w-full h-auto origin-top-left"
            :style="{ transform: `scale(${zoom})` }"
          />
        </div>
      </div>

      <div v-else-if="isPdf" class="h-full">
        <iframe class="w-full h-full" :src="viewUrl" sandbox="" referrerpolicy="no-referrer" />
      </div>

      <div v-else-if="isHtml && text !== null" class="h-full">
        <HtmlRenderer :html="text" />
      </div>

      <div v-else-if="(isCsv || isJson) && text !== null" class="p-4">
        <div class="flex items-center justify-between gap-2 mb-2">
          <input
            v-model="query"
            type="text"
            class="w-full p-2 text-sm border border-slate-200 rounded bg-white"
            placeholder="Buscar…"
          />
          <select v-model.number="pageSize" class="p-2 text-sm border border-slate-200 rounded bg-white">
            <option :value="10">10</option>
            <option :value="25">25</option>
            <option :value="50">50</option>
          </select>
        </div>

        <div class="text-xs text-slate-500 mb-2">
          Mostrando {{ filtered.length }} fila(s) (hasta 500 en preview)
        </div>

        <div v-if="rows.length" class="overflow-auto border border-slate-200 rounded-lg shadow-sm bg-white">
          <table class="min-w-full text-xs text-slate-600">
            <thead class="bg-gray-100 sticky top-0 text-slate-800 font-semibold uppercase tracking-wider">
              <tr>
                <th
                  v-for="c in columns"
                  :key="c"
                  class="text-left px-3 py-2 border-b border-r border-slate-200 last:border-r-0"
                >
                  {{ c }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, idx) in paged" :key="idx" class="odd:bg-white even:bg-slate-50">
                <td v-for="c in columns" :key="c" class="px-3 py-2 border-b border-slate-100 align-top">
                  {{ (r as any)[c] }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="rows.length" class="flex items-center justify-between mt-2 text-sm">
          <button
            class="px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50"
            type="button"
            :disabled="page <= 1"
            @click="page = Math.max(1, page - 1)"
          >
            Anterior
          </button>
          <div class="text-xs text-slate-500">Página {{ page }} / {{ totalPages }}</div>
          <button
            class="px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50"
            type="button"
            :disabled="page >= totalPages"
            @click="page = Math.min(totalPages, page + 1)"
          >
            Siguiente
          </button>
        </div>

        <div v-if="rawPreview" class="mt-4">
          <div class="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Raw Preview</div>
          <div class="bg-white border border-slate-200 rounded-lg p-3 overflow-x-auto">
            <pre class="text-[10px] leading-relaxed font-mono text-slate-600">{{ rawPreview }}</pre>
          </div>
        </div>
      </div>

      <div v-else-if="isCode && text !== null" class="p-3">
        <SyntaxHighlighter :code="text" :language="language" />
      </div>

      <div v-else-if="text !== null" class="p-3">
        <pre class="text-sm whitespace-pre-wrap bg-white border border-slate-200 rounded p-3 overflow-auto">{{ text }}</pre>
      </div>

      <div v-else class="p-4 text-sm text-slate-500">
        No se pudo previsualizar este archivo.
      </div>
    </div>
    <div class="p-3 bg-white border-t border-slate-200 text-center">
      <p class="text-[10px] text-slate-400 flex items-center justify-center gap-1">
        <span class="material-icons-outlined text-xs">info</span>
        Generado por Navibot · {{ file.modified_at }}
      </p>
    </div>
  </div>
</template>
