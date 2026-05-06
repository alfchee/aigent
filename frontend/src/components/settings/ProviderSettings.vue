<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Eye, EyeOff, Check, X, Loader2, AlertCircle, Wifi } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import {
  fetchProviders,
  updateProviders,
  testProvider,
  fetchProviderModels,
  type ProviderStatus,
  type ProviderUpdate,
  type TestProviderResult,
} from '@/services/configApi'

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const providers = ref<ProviderStatus[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref<string | null>(null)
const saveSuccess = ref(false)

// Per-provider UI state
type ProviderUIState = {
  keyVisible: boolean
  draftKey: string // what the user has typed; empty = unchanged
  draftBaseUrl: string
  draftDefaultModel: string
  testing: boolean
  testResult: TestProviderResult | null
  detectingModels: boolean
  detectedModels: string[]
}

const uiState = ref<Record<string, ProviderUIState>>({})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function initUiState(ps: ProviderStatus[]) {
  for (const p of ps) {
    uiState.value[p.name] = {
      keyVisible: false,
      draftKey: '',
      draftBaseUrl: p.base_url ?? '',
      draftDefaultModel: p.default_model ?? '',
      testing: false,
      testResult: null,
      detectingModels: false,
      detectedModels: [],
    }
  }
}

function statusColor(status: ProviderStatus['status']) {
  if (status === 'configured') return 'text-green-500'
  if (status === 'missing') return 'text-red-500'
  return 'text-yellow-500'
}

function statusDot(status: ProviderStatus['status']) {
  if (status === 'configured') return '🟢'
  if (status === 'missing') return '🔴'
  return '🟡'
}

function statusLabel(status: ProviderStatus['status']) {
  if (status === 'configured') return 'Configured'
  if (status === 'missing') return 'Missing key'
  return 'Untested'
}

// ---------------------------------------------------------------------------
// Input handlers (type casts not allowed in Vue templates)
// ---------------------------------------------------------------------------

function onKeyInput(name: string, event: Event) {
  uiState.value[name].draftKey = (event.target as HTMLInputElement).value
}

function onBaseUrlInput(event: Event) {
  uiState.value['ollama'].draftBaseUrl = (event.target as HTMLInputElement).value
}

function onModelChange(name: string, event: Event) {
  uiState.value[name].draftDefaultModel = (event.target as HTMLSelectElement).value
}

function testResultFor(name: string) {
  return uiState.value[name]?.testResult ?? null
}

// ---------------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------------

async function load() {
  loading.value = true
  error.value = null
  try {
    providers.value = await fetchProviders()
    initUiState(providers.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load providers'
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

async function handleTest(name: string) {
  const ui = uiState.value[name]
  if (!ui) return
  ui.testing = true
  ui.testResult = null
  try {
    ui.testResult = await testProvider(name)
  } catch (err) {
    ui.testResult = {
      success: false,
      message: err instanceof Error ? err.message : 'Unknown error',
      latency_ms: null,
    }
  } finally {
    ui.testing = false
  }
}

// ---------------------------------------------------------------------------
// Detect local Ollama models
// ---------------------------------------------------------------------------

async function detectOllamaModels() {
  const ui = uiState.value['ollama']
  if (!ui) return
  ui.detectingModels = true
  ui.detectedModels = []
  try {
    ui.detectedModels = await fetchProviderModels('ollama')
    if (ui.detectedModels.length > 0 && !ui.draftDefaultModel) {
      ui.draftDefaultModel = ui.detectedModels[0]
    }
  } catch {
    ui.detectedModels = []
  } finally {
    ui.detectingModels = false
  }
}

// ---------------------------------------------------------------------------
// Save
// ---------------------------------------------------------------------------

async function handleSave() {
  saving.value = true
  saveSuccess.value = false
  error.value = null

  const updates: ProviderUpdate[] = []

  for (const p of providers.value) {
    const ui = uiState.value[p.name]
    if (!ui) continue

    const update: ProviderUpdate = { name: p.name }
    let dirty = false

    if (ui.draftKey !== '') {
      update.api_key = ui.draftKey
      dirty = true
    }

    const newBaseUrl = ui.draftBaseUrl.trim() || null
    if (newBaseUrl !== (p.base_url ?? null)) {
      update.base_url = newBaseUrl
      dirty = true
    }

    const newModel = ui.draftDefaultModel.trim() || null
    if (newModel !== (p.default_model ?? null)) {
      update.default_model = newModel
      dirty = true
    }

    if (dirty) updates.push(update)
  }

  if (updates.length === 0) {
    saving.value = false
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 2000)
    return
  }

  try {
    providers.value = await updateProviders(updates)
    // Re-init ui state from fresh provider data (keeps draftKey cleared)
    for (const p of providers.value) {
      const ui = uiState.value[p.name]
      if (ui) {
        ui.draftKey = ''
        ui.draftBaseUrl = p.base_url ?? ''
        ui.draftDefaultModel = p.default_model ?? ''
        ui.testResult = null
      }
    }
    saveSuccess.value = true
    error.value = null
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save providers'
    // Keep draft state on error for user to retry
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h3 class="text-sm font-semibold text-text">Provider Settings</h3>
      <p class="text-xs text-muted mt-1">
        Manage API keys for LLM providers. Keys are stored encrypted on the server and
        never returned in plain text. Changes take effect immediately without a restart.
      </p>
    </div>

    <!-- Error banner -->
    <div
      v-if="error"
      class="flex items-center gap-2 text-danger text-sm bg-danger/10 p-3 rounded-lg"
    >
      <AlertCircle class="w-4 h-4 shrink-0" />
      {{ error }}
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-4">
      <div v-for="i in 6" :key="i" class="h-20 rounded-xl bg-surface2 animate-pulse" />
    </div>

    <!-- Provider rows -->
    <div v-else class="space-y-3">
      <div
        v-for="provider in providers"
        :key="provider.name"
        class="rounded-xl border border-border bg-surface p-4 space-y-3"
      >
        <!-- Row header: label + status badge -->
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-text">{{ provider.label }}</span>
            <span :class="['text-xs font-medium', statusColor(provider.status)]">
              {{ statusDot(provider.status) }} {{ statusLabel(provider.status) }}
            </span>
          </div>

          <!-- Test button -->
          <Button
            size="sm"
            variant="ghost"
            :disabled="uiState[provider.name]?.testing"
            @click="handleTest(provider.name)"
          >
            <Loader2
              v-if="uiState[provider.name]?.testing"
              class="w-3.5 h-3.5 animate-spin"
            />
            <Wifi v-else class="w-3.5 h-3.5" />
            Test
          </Button>
        </div>

        <!-- Test result inline -->
        <template v-if="testResultFor(provider.name)">
          <div
            :class="[
              'flex items-center gap-2 text-xs px-3 py-2 rounded-lg',
              testResultFor(provider.name)?.success
                ? 'text-green-700 bg-green-500/10'
                : 'text-danger bg-danger/10',
            ]"
          >
            <Check v-if="testResultFor(provider.name)?.success" class="w-3.5 h-3.5" />
            <X v-else class="w-3.5 h-3.5" />
            {{ testResultFor(provider.name)?.message }}
            <span
              v-if="testResultFor(provider.name)?.latency_ms !== null"
              class="ml-auto text-muted"
            >
              {{ testResultFor(provider.name)?.latency_ms }} ms
            </span>
          </div>
        </template>

        <!-- API key input (hidden for Ollama) -->
        <div v-if="provider.needs_key" class="relative">
          <label class="grid gap-1.5">
            <span class="text-xs text-muted">API Key</span>
            <div class="relative">
              <input
                :type="uiState[provider.name]?.keyVisible ? 'text' : 'password'"
                class="w-full h-10 rounded-xl border border-border bg-surface2 px-3 pr-10 text-sm text-text outline-none transition focus-visible:ring-2 focus-visible:ring-brand/40 placeholder:text-muted"
                :placeholder="provider.has_key ? '••••••••••••••••' : 'Paste API key…'"
                :value="uiState[provider.name]?.draftKey"
                autocomplete="off"
                @input="onKeyInput(provider.name, $event)"
              />
              <button
                type="button"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text transition"
                :aria-label="uiState[provider.name]?.keyVisible ? 'Hide key' : 'Show key'"
                @click="
                  uiState[provider.name].keyVisible = !uiState[provider.name].keyVisible
                "
              >
                <EyeOff v-if="uiState[provider.name]?.keyVisible" class="w-4 h-4" />
                <Eye v-else class="w-4 h-4" />
              </button>
            </div>
          </label>
        </div>

        <!-- Ollama: Base URL + detect models -->
        <template v-if="provider.name === 'ollama'">
          <label class="grid gap-1.5">
            <span class="text-xs text-muted">Base URL</span>
            <input
              type="text"
              class="h-10 rounded-xl border border-border bg-surface2 px-3 text-sm text-text outline-none transition focus-visible:ring-2 focus-visible:ring-brand/40"
              placeholder="http://localhost:11434"
              :value="uiState['ollama']?.draftBaseUrl"
              @input="onBaseUrlInput($event)"
            />
          </label>

          <div class="flex items-center gap-3">
            <Button
              size="sm"
              variant="ghost"
              :disabled="uiState['ollama']?.detectingModels"
              @click="detectOllamaModels"
            >
              <Loader2
                v-if="uiState['ollama']?.detectingModels"
                class="w-3.5 h-3.5 animate-spin"
              />
              Detect local models
            </Button>
            <span
              v-if="uiState['ollama']?.detectedModels.length > 0"
              class="text-xs text-muted"
            >
              Found: {{ uiState['ollama'].detectedModels.join(', ') }}
            </span>
            <span
              v-else-if="
                !uiState['ollama']?.detectingModels &&
                uiState['ollama']?.detectedModels.length === 0 &&
                uiState['ollama']?.testResult
              "
              class="text-xs text-muted"
            >
              No models found
            </span>
          </div>
        </template>

        <!-- Default model selector -->
        <label class="grid gap-1.5">
          <span class="text-xs text-muted">Default model</span>
          <select
            class="h-10 rounded-xl border border-border bg-surface2 px-3 text-sm text-text outline-none transition focus-visible:ring-2 focus-visible:ring-brand/40 cursor-pointer"
            :value="uiState[provider.name]?.draftDefaultModel"
            @change="onModelChange(provider.name, $event)"
          >
            <option value="">— use provider default —</option>
            <!-- Show detected Ollama models if available, otherwise show provider models -->
            <template
              v-if="
                provider.name === 'ollama' && uiState['ollama']?.detectedModels.length > 0
              "
            >
              <option v-for="m in uiState['ollama'].detectedModels" :key="m" :value="m">
                {{ m }}
              </option>
            </template>
            <!-- Fallback to provider models or empty list for Ollama without detection -->
            <template v-else-if="provider.available_models.length > 0">
              <option v-for="m in provider.available_models" :key="m" :value="m">
                {{ m }}
              </option>
            </template>
            <template v-else>
              <option disabled>No models available</option>
            </template>
          </select>
        </label>
      </div>
    </div>

    <!-- Save bar -->
    <div class="flex items-center justify-between pt-2">
      <span v-if="saveSuccess" class="flex items-center gap-1.5 text-sm text-green-600">
        <Check class="w-4 h-4" />
        Saved
      </span>
      <span v-else />

      <Button variant="primary" :disabled="loading || saving" @click="handleSave">
        <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
        Save changes
      </Button>
    </div>
  </div>
</template>
