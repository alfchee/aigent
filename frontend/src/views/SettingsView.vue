<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useModelSettingsStore } from '../stores/modelSettings'

const store = useModelSettingsStore()

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const saveOk = ref(false)

// Local state for editing
const currentModel = ref('')
const fallbackModel = ref('')
const autoEscalate = ref(true)
const systemPrompt = ref('')

// Read-only data from store
const providers = computed(() => store.providers)
const models = computed(() => store.models)
const fastModels = computed(() => store.fastModels)
const fallbackModels = computed(() => store.fallbackModels)

const canSave = computed(() => !saving.value && Boolean(currentModel.value.trim()) && Boolean(fallbackModel.value.trim()))

async function load() {
  loading.value = true
  error.value = null
  saveOk.value = false
  try {
    await store.loadAppSettings()
    // Sync local state with store
    currentModel.value = store.currentModel
    fallbackModel.value = store.fallbackModel
    autoEscalate.value = store.autoEscalate
    systemPrompt.value = store.systemPrompt
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = null
  saveOk.value = false
  try {
    const payload = {
      current_model: currentModel.value,
      fallback_model: fallbackModel.value,
      auto_escalate: autoEscalate.value,
      system_prompt: systemPrompt.value
    }
    await store.updateAppSettings(payload)
    
    // Re-sync local state
    currentModel.value = store.currentModel
    fallbackModel.value = store.fallbackModel
    autoEscalate.value = store.autoEscalate
    systemPrompt.value = store.systemPrompt
    
    saveOk.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="p-4 bg-white border-b border-slate-200 flex items-center justify-between shadow-sm">
      <div class="flex items-center gap-3">
        <RouterLink
          to="/"
          class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50"
        >
          Volver
        </RouterLink>
        <div class="text-sm font-semibold text-slate-800">Settings</div>
      </div>
      <button
        type="button"
        class="text-xs px-3 py-2 rounded bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-50"
        :disabled="!canSave"
        @click="save"
      >
        {{ saving ? 'Guardando…' : 'Guardar' }}
      </button>
    </header>

    <main class="p-4 md:p-8 max-w-3xl mx-auto space-y-6">
      <div v-if="loading" class="text-sm text-slate-500">Cargando…</div>
      <div v-else class="space-y-6">
        <div v-if="error" class="text-sm text-red-600 border border-red-200 bg-red-50 rounded-xl p-3">
          {{ error }}
        </div>
        <div v-else-if="saveOk" class="text-sm text-emerald-700 border border-emerald-200 bg-emerald-50 rounded-xl p-3">
          Guardado correctamente.
        </div>

        <section class="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
          <div class="text-sm font-semibold text-slate-800">Modelos</div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label class="space-y-1">
              <div class="text-xs text-slate-600">Modelo por defecto</div>
              <select
                v-model="currentModel"
                class="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-sm"
              >
                <option v-for="m in (fastModels.length ? fastModels : models)" :key="m" :value="m">{{ m }}</option>
              </select>
            </label>

            <label class="space-y-1">
              <div class="text-xs text-slate-600">Modelo fallback (auto-escalación)</div>
              <select
                v-model="fallbackModel"
                class="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-sm"
              >
                <option v-for="m in (fallbackModels.length ? fallbackModels : models)" :key="m" :value="m">{{ m }}</option>
              </select>
            </label>
          </div>

          <label class="flex items-center gap-2 text-sm">
            <input type="checkbox" v-model="autoEscalate" class="h-4 w-4" />
            <span>Auto-escalación (reintenta una vez con fallback cuando falla)</span>
          </label>
        </section>

        <section class="bg-white border border-slate-200 rounded-2xl p-5 space-y-3">
          <div class="text-sm font-semibold text-slate-800">System Prompt</div>
          <textarea
            v-model="systemPrompt"
            rows="8"
            class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono"
            placeholder="Instrucciones globales del agente…"
          ></textarea>
        </section>

        <section class="bg-white border border-slate-200 rounded-2xl p-5 space-y-2">
          <div class="text-sm font-semibold text-slate-800">Providers</div>
          <div class="text-xs text-slate-600">
            Google: <span :class="providers.google ? 'text-emerald-700' : 'text-amber-700'">{{ providers.google ? 'configurada' : 'no configurada' }}</span>
          </div>
          <div class="text-xs text-slate-600">
            OpenAI: <span :class="providers.openai ? 'text-emerald-700' : 'text-amber-700'">{{ providers.openai ? 'configurada' : 'no configurada' }}</span>
          </div>
          <div class="text-xs text-slate-600">
            Brave: <span :class="providers.brave ? 'text-emerald-700' : 'text-amber-700'">{{ providers.brave ? 'configurada' : 'no configurada' }}</span>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>
