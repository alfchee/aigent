<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { useChatStore } from '../../stores/chat'
import { useArtifactsStore } from '../../stores/artifacts'
import { useModelSettingsStore } from '../../stores/modelSettings'
import ChatMessage from './ChatMessage.vue'
import { FEATURES } from '../../lib/featureFlags'

const chat = useChatStore()
const artifacts = useArtifactsStore()
const modelSettings = useModelSettingsStore()
const newMessage = ref('')
const selectedModel = ref('')
const isExpanded = ref(false)
const composerRef = ref<HTMLTextAreaElement | null>(null)

const messages = computed(() => chat.messages)
const isLoading = computed(() => chat.isLoading)
const isHistoryLoading = computed(() => chat.isHistoryLoading)
const historyHasMore = computed(() => chat.historyHasMore)
const historyError = computed(() => chat.historyError)
const primaryModel = computed(() => modelSettings.currentModel)
const fallbackModel = computed(() => modelSettings.fallbackModel)
const effectiveModel = computed(() => selectedModel.value || primaryModel.value || '')
const effectiveSource = computed(() => {
  if (!effectiveModel.value) return ''
  if (selectedModel.value && selectedModel.value !== primaryModel.value) return 'Sesión'
  return 'Principal'
})
const modelOptions = computed(() => {
  const options = [...modelSettings.models]
  const ensure = (name: string) => {
    if (name && !options.includes(name)) options.push(name)
  }
  ensure(primaryModel.value)
  ensure(fallbackModel.value)
  ensure(selectedModel.value)
  return options
})
const availableModelMap = computed(() => {
  return modelSettings.availableModels.reduce<Record<string, { display_name?: string }>>((acc, model) => {
    acc[model.id] = model
    return acc
  }, {})
})

const scrollRef = ref<HTMLElement | null>(null)

async function send() {
  const msg = newMessage.value
  newMessage.value = ''
  await chat.sendMessage(msg, artifacts.sessionId, selectedModel.value || undefined)
}

async function handleComposerKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  if (event.shiftKey || event.isComposing) return
  event.preventDefault()
  await send()
}

async function loadMore() {
  await chat.loadMoreHistory(artifacts.sessionId)
}

const MODEL_LABELS: Record<string, string> = {
  'gemini-3-flash-preview': 'Fast (Gemini 3 Flash Preview)',
  'gemini-flash-latest': 'Fast (Gemini Flash Latest)',
  'gemini-3-pro-preview': 'Pro (Gemini 3 Pro Preview)',
  'gemini-2.5-pro': 'Pro (Gemini 2.5 Pro)'
}

const MODEL_ICONS: Record<string, string> = {
  'gemini-3-flash-preview': '⚡',
  'gemini-flash-latest': '⚡',
  'gemini-3-pro-preview': '🧠',
  'gemini-2.5-pro': '🧠'
}

function normalizeModelLabel(label: string) {
  return label.replace(/^(⚡|🧠)\s*/u, '').trim()
}

function modelLabel(name: string) {
  const baseLabel = availableModelMap.value[name]?.display_name || MODEL_LABELS[name] || name
  const normalized = normalizeModelLabel(baseLabel)
  const icon = MODEL_ICONS[name]
  return icon ? `${icon} ${normalized}` : normalized
}

function modelOptionLabel(name: string) {
  const label = modelLabel(name)
  const tags: string[] = []
  if (name && name === primaryModel.value) tags.push('Principal')
  if (name && name === fallbackModel.value) tags.push('Fallback')
  if (name && name === selectedModel.value && name !== primaryModel.value) tags.push('Sesión')
  return tags.length ? `${label} (${tags.join(' • ')})` : label
}

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  nextTick(() => {
    composerRef.value?.focus()
  })
}

async function syncModelForSession(sessionId: string) {
  if (!modelSettings.models.length) {
    await modelSettings.loadAppSettings()
  }
  await modelSettings.loadSessionModel(sessionId)
  const sid = sessionId || 'default'
  selectedModel.value = modelSettings.sessionModels[sid] || modelSettings.currentModel || ''
}

watch(
  () => artifacts.sessionId,
  async (sid) => {
    await syncModelForSession(sid)
  },
  { immediate: true }
)

watch(
  () => [modelSettings.currentModel, modelSettings.fallbackModel, modelSettings.models.length],
  async () => {
    if (!modelSettings.models.length) return
    const sid = artifacts.sessionId || 'default'
    const sessionModel = modelSettings.sessionModels[sid]
    if (!sessionModel && modelSettings.currentModel) {
      selectedModel.value = modelSettings.currentModel
    }
  }
)

watch(
  () => selectedModel.value,
  async (next, prev) => {
    if (!next || next === prev) return
    const sid = artifacts.sessionId || 'default'
    try {
      await modelSettings.setSessionModel(sid, next)
    } catch {
    }
  }
)

watch(
  () => chat.messages.length,
  async () => {
    await nextTick()
    scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight })
  }
)
</script>

<template>
  <div class="h-full flex flex-col bg-slate-50 overflow-hidden">
    <div ref="scrollRef" class="flex-1 min-h-0 overflow-y-auto p-4 md:p-8 flex flex-col items-center bg-slate-50/50 bg-pattern">
      <div class="w-full max-w-3xl space-y-6">
        <div class="flex items-center justify-center">
          <button
            v-if="historyHasMore"
            type="button"
            class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50"
            :disabled="isHistoryLoading"
            @click="loadMore"
          >
            {{ isHistoryLoading ? 'Cargando…' : 'Cargar mensajes anteriores' }}
          </button>
          <div v-else-if="isHistoryLoading" class="text-xs text-slate-500">Cargando…</div>
        </div>
        <div v-if="historyError" class="text-xs text-red-600 text-center">
          Error al cargar historial: {{ historyError }}
        </div>
        <div
          v-for="(msg, index) in messages"
          :key="msg.id ?? index"
          :class="['flex w-full animate-in fade-in slide-in-from-bottom-2 duration-300', msg.role === 'user' ? 'justify-end' : 'justify-start']"
        >
          <ChatMessage :role="msg.role" :content="msg.content" />
        </div>

        <div v-if="isLoading" class="flex justify-start animate-pulse">
          <div class="bg-white p-4 rounded-2xl border border-slate-100 shadow-md flex items-center gap-3">
            <div class="flex gap-1">
              <span class="w-2 h-2 bg-sky-400 rounded-full animate-bounce"></span>
              <span class="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
              <span class="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
            </div>
            <span class="text-xs text-slate-500 font-medium">Pensando...</span>
          </div>
        </div>
      </div>
    </div>

    <div class="shrink-0 p-4 md:p-6 max-w-4xl mx-auto w-full">
      <div class="bg-white rounded-xl shadow-lg border border-slate-200 p-2 flex flex-col gap-2">
        <textarea
          v-model="newMessage"
          placeholder="Escribe un mensaje..."
          ref="composerRef"
          :rows="isExpanded ? 5 : 2"
          class="w-full bg-transparent border-none focus:ring-0 text-slate-800 placeholder-slate-400 resize-none py-3 px-3 text-sm leading-relaxed transition-all duration-200 ease-in-out min-h-[72px]"
          :class="isExpanded ? 'min-h-[160px]' : 'min-h-[72px]'"
          :disabled="isLoading"
          aria-label="Escribe un mensaje"
          @keydown="handleComposerKeydown"
        ></textarea>
        <div class="flex items-center justify-between px-2 pb-1">
          <div class="relative group">
            <select
              v-model="selectedModel"
              class="appearance-none pl-8 pr-8 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors text-xs font-medium text-slate-700 bg-transparent cursor-pointer focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              :disabled="isLoading || !modelSettings.models.length"
              title="Modelo"
            >
              <option v-for="m in modelOptions" :key="m" :value="m">{{ modelOptionLabel(m) }}</option>
            </select>
            <span class="material-icons-outlined text-sm text-slate-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">expand_more</span>
            <div class="mt-1 flex flex-wrap gap-1 text-[10px] text-slate-500">
              <span v-if="effectiveModel" class="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">Usando: {{ modelLabel(effectiveModel) }} ({{ effectiveSource }})</span>
              <span v-if="primaryModel" class="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">Principal: {{ modelLabel(primaryModel) }}</span>
              <span v-if="fallbackModel" class="px-2 py-0.5 rounded bg-slate-100 border border-slate-200">Fallback: {{ modelLabel(fallbackModel) }}</span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <div class="flex items-center gap-1 mr-2 border-r border-slate-200 pr-3">
              <button
                class="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                title="Locate (Requires implementation)"
                :disabled="!FEATURES.LOCATE_SKILL"
              >
                <span class="material-icons-outlined text-lg">location_on</span>
              </button>
              <button
                class="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                title="Drive (Requires implementation)"
                :disabled="!FEATURES.DRIVE_SKILL"
              >
                <span class="material-icons-outlined text-lg">add_to_drive</span>
              </button>
            </div>
            <button
              type="button"
              class="p-2 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
              :aria-label="isExpanded ? 'Contraer editor' : 'Expandir editor'"
              @click="toggleExpand"
            >
              <span class="material-icons-outlined text-lg">{{ isExpanded ? 'unfold_less' : 'unfold_more' }}</span>
            </button>
            <button
              type="button"
              :disabled="isLoading || !newMessage.trim()"
              class="p-2 bg-sky-500 hover:bg-sky-600 text-white rounded-lg transition-colors shadow-sm flex items-center justify-center disabled:opacity-50 disabled:bg-slate-300"
              @click="send"
            >
              <span class="material-icons-outlined text-lg transform -rotate-45 translate-x-0.5 -translate-y-0.5">send</span>
            </button>
          </div>
        </div>
      </div>
      <div class="text-center mt-2">
        <span class="text-[10px] text-slate-400">© 2026 Navibot Agent</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bg-pattern {
  background-image: radial-gradient(rgba(0, 0, 0, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
}
</style>
