<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useModelSettingsStore } from '../stores/modelSettings'

const store = useModelSettingsStore()

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const saveOk = ref(false)
const activeTab = ref('general')

// Local state for editing
const currentModel = ref('')
const fallbackModel = ref('')
const autoEscalate = ref(true)
const systemPrompt = ref('')

// Limits
const executionTimeout = ref(300)
const maxSearchResults = ref(5)
const maxRetries = ref(1)

// Advanced JSON
const jsonContent = ref('')
const jsonError = ref<string | null>(null)

// Read-only data from store
const providers = computed(() => store.providers)
const models = computed(() => store.models)
const availableModels = computed(() => store.availableModels)

// Use availableModels if present, otherwise fall back to static lists
const dynamicModels = computed(() => {
  if (availableModels.value.length > 0) {
    return availableModels.value.map(m => m.id)
  }
  return models.value
})

const canSave = computed(() => {
  if (saving.value) return false
  if (activeTab.value === 'advanced' && jsonError.value) return false
  return Boolean(currentModel.value.trim()) && Boolean(fallbackModel.value.trim())
})

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
    
    // Limits
    if (store.limitsConfig) {
      executionTimeout.value = store.limitsConfig.execution_timeout_seconds ?? 300
      maxSearchResults.value = store.limitsConfig.max_search_results ?? 5
      maxRetries.value = store.limitsConfig.max_retries ?? 1
    }
    
    // JSON
    jsonContent.value = JSON.stringify(store.modelRoutingJson || {}, null, 2)
    
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

watch(jsonContent, (newVal) => {
  try {
    JSON.parse(newVal)
    jsonError.value = null
  } catch (e) {
    jsonError.value = 'JSON inválido'
  }
})

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = null
  saveOk.value = false
  
  try {
    const payload: any = {
      current_model: currentModel.value,
      fallback_model: fallbackModel.value,
      auto_escalate: autoEscalate.value,
      system_prompt: systemPrompt.value,
      limits_config: {
        execution_timeout_seconds: Number(executionTimeout.value),
        max_search_results: Number(maxSearchResults.value),
        max_retries: Number(maxRetries.value)
      }
    }
    
    // Only send JSON if we are in Advanced tab or if we want to ensure sync
    // But actually, if user edits JSON, that overrides other settings potentially if they overlap
    // The backend logic says: if model_routing_json is present, it updates routing_config.
    // So if we are in Advanced tab, we send model_routing_json.
    if (activeTab.value === 'advanced') {
       try {
         payload.model_routing_json = JSON.parse(jsonContent.value)
       } catch (e) {
         throw new Error('JSON inválido en pestaña Avanzado')
       }
    }
    
    await store.updateAppSettings(payload)
    
    // Re-sync local state
    currentModel.value = store.currentModel
    fallbackModel.value = store.fallbackModel
    autoEscalate.value = store.autoEscalate
    systemPrompt.value = store.systemPrompt
    if (store.limitsConfig) {
      executionTimeout.value = store.limitsConfig.execution_timeout_seconds ?? 300
      maxSearchResults.value = store.limitsConfig.max_search_results ?? 5
      maxRetries.value = store.limitsConfig.max_retries ?? 1
    }
    jsonContent.value = JSON.stringify(store.modelRoutingJson || {}, null, 2)
    
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
  <div class="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
    <header class="p-4 bg-white border-b border-slate-200 flex items-center justify-between shadow-sm sticky top-0 z-10">
      <div class="flex items-center gap-3">
        <RouterLink
          to="/"
          class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50"
          aria-label="Volver"
        >
          Volver
        </RouterLink>
        <div class="text-sm font-semibold text-slate-800">Command Center</div>
      </div>
      <div class="flex items-center gap-2">
         <span v-if="saveOk" class="text-xs text-emerald-600 font-medium animate-pulse">Guardado</span>
         <button
          type="button"
          class="text-xs px-4 py-2 rounded bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-50 font-medium transition-colors"
          :disabled="!canSave"
          @click="save"
        >
          {{ saving ? 'Guardando…' : 'Guardar Cambios' }}
        </button>
      </div>
    </header>

    <main class="flex-1 p-4 md:p-8 max-w-5xl mx-auto w-full space-y-6">
      <div v-if="loading" class="text-center py-12 text-slate-500">
        <div class="animate-spin h-8 w-8 border-4 border-sky-500 border-t-transparent rounded-full mx-auto mb-2"></div>
        Cargando configuración...
      </div>
      
      <div v-else class="space-y-6">
        <div v-if="error" class="text-sm text-red-600 border border-red-200 bg-red-50 rounded-xl p-4 flex items-start gap-2">
           <svg class="w-5 h-5 text-red-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
           <div>{{ error }}</div>
        </div>

        <!-- Tabs -->
        <div class="flex border-b border-slate-200 space-x-1 overflow-x-auto">
          <button
            v-for="tab in ['general', 'personality', 'limits', 'advanced']"
            :key="tab"
            @click="activeTab = tab"
            class="px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap capitalize"
            :class="activeTab === tab ? 'border-sky-500 text-sky-600' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'"
          >
            {{ tab }}
          </button>
        </div>

        <!-- Tab Content -->
        <div class="bg-white border border-slate-200 rounded-2xl shadow-sm min-h-[400px]">
          
          <!-- GENERAL TAB -->
          <div v-if="activeTab === 'general'" class="p-6 space-y-8">
            <section class="space-y-4">
              <h3 class="text-base font-semibold text-slate-800 flex items-center gap-2">
                <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                Modelos y Comportamiento
              </h3>
              
              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-2">
                  <label class="block text-sm font-medium text-slate-700">Modelo Principal (Rápido)</label>
                  <div class="relative">
                    <select
                      v-model="currentModel"
                      class="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none"
                    >
                      <option v-for="m in dynamicModels" :key="m" :value="m">{{ m }}</option>
                    </select>
                  </div>
                  <p class="text-xs text-slate-500">Usado por defecto para tareas simples y rápidas.</p>
                </div>

                <div class="space-y-2">
                  <label class="block text-sm font-medium text-slate-700">Modelo Fallback (Inteligente)</label>
                  <div class="relative">
                    <select
                      v-model="fallbackModel"
                      class="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none"
                    >
                      <option v-for="m in dynamicModels" :key="m" :value="m">{{ m }}</option>
                    </select>
                  </div>
                  <p class="text-xs text-slate-500">Usado para razonamiento complejo o cuando el principal falla.</p>
                </div>
              </div>

              <div class="bg-sky-50 border border-sky-100 rounded-lg p-4 flex items-start gap-3">
                 <div class="flex items-center h-5">
                   <input type="checkbox" v-model="autoEscalate" id="autoEscalate" class="h-4 w-4 text-sky-600 focus:ring-sky-500 border-gray-300 rounded" />
                 </div>
                 <div class="ml-0">
                   <label for="autoEscalate" class="font-medium text-slate-900 text-sm">Activar Inteligencia Adaptativa</label>
                   <p class="text-slate-600 text-xs mt-1">Si el modelo principal falla o encuentra errores técnicos, el sistema reintentará automáticamente con el modelo Inteligente.</p>
                 </div>
              </div>
            </section>

            <section class="space-y-4 pt-6 border-t border-slate-100">
               <h3 class="text-base font-semibold text-slate-800 flex items-center gap-2">
                <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                Estado de Proveedores
              </h3>
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                 <div class="p-3 rounded-lg border flex items-center justify-between" :class="providers.google ? 'bg-emerald-50 border-emerald-100' : 'bg-slate-50 border-slate-200'">
                    <span class="text-sm font-medium text-slate-700">Google Gemini</span>
                    <span class="text-xs font-bold px-2 py-1 rounded" :class="providers.google ? 'bg-emerald-200 text-emerald-800' : 'bg-slate-200 text-slate-500'">{{ providers.google ? 'ACTIVO' : 'INACTIVO' }}</span>
                 </div>
                 <div class="p-3 rounded-lg border flex items-center justify-between" :class="providers.openai ? 'bg-emerald-50 border-emerald-100' : 'bg-slate-50 border-slate-200'">
                    <span class="text-sm font-medium text-slate-700">OpenAI</span>
                    <span class="text-xs font-bold px-2 py-1 rounded" :class="providers.openai ? 'bg-emerald-200 text-emerald-800' : 'bg-slate-200 text-slate-500'">{{ providers.openai ? 'ACTIVO' : 'INACTIVO' }}</span>
                 </div>
                 <div class="p-3 rounded-lg border flex items-center justify-between" :class="providers.brave ? 'bg-emerald-50 border-emerald-100' : 'bg-slate-50 border-slate-200'">
                    <span class="text-sm font-medium text-slate-700">Brave Search</span>
                    <span class="text-xs font-bold px-2 py-1 rounded" :class="providers.brave ? 'bg-emerald-200 text-emerald-800' : 'bg-slate-200 text-slate-500'">{{ providers.brave ? 'ACTIVO' : 'INACTIVO' }}</span>
                 </div>
              </div>
            </section>
          </div>

          <!-- PERSONALITY TAB -->
          <div v-if="activeTab === 'personality'" class="p-6 space-y-6">
             <div class="flex items-start gap-4">
               <div class="flex-1 space-y-4">
                  <div class="space-y-1">
                    <h3 class="text-base font-semibold text-slate-800">System Prompt</h3>
                    <p class="text-sm text-slate-500">Define la identidad, el tono y las reglas fundamentales de comportamiento del agente.</p>
                  </div>
                  <textarea
                    v-model="systemPrompt"
                    rows="15"
                    class="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono leading-relaxed focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none resize-none"
                    placeholder="Eres NaviBot, un asistente experto..."
                  ></textarea>
               </div>
               <div class="w-64 bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3 hidden md:block">
                  <h4 class="text-xs font-bold text-slate-500 uppercase tracking-wider">Tips</h4>
                  <ul class="text-xs text-slate-600 space-y-2 list-disc pl-4">
                    <li>Define claramente el rol.</li>
                    <li>Especifica el formato de salida deseado.</li>
                    <li>Establece restricciones de seguridad.</li>
                    <li>Usa ejemplos para guiar el estilo.</li>
                  </ul>
               </div>
             </div>
          </div>

          <!-- LIMITS TAB -->
          <div v-if="activeTab === 'limits'" class="p-6 space-y-8">
             <h3 class="text-base font-semibold text-slate-800">Límites y Restricciones</h3>
             
             <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-2">
                  <label class="block text-sm font-medium text-slate-700">Timeout de Ejecución (segundos)</label>
                  <input
                    type="number"
                    v-model="executionTimeout"
                    class="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm"
                  />
                  <p class="text-xs text-slate-500">Tiempo máximo que el agente esperará una respuesta de una herramienta.</p>
                </div>

                <div class="space-y-2">
                  <label class="block text-sm font-medium text-slate-700">Resultados de Búsqueda Máximos</label>
                  <input
                    type="number"
                    v-model="maxSearchResults"
                    class="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm"
                  />
                  <p class="text-xs text-slate-500">Número máximo de enlaces que el agente recuperará por búsqueda.</p>
                </div>
                
                 <div class="space-y-2">
                  <label class="block text-sm font-medium text-slate-700">Reintentos Máximos</label>
                  <input
                    type="number"
                    v-model="maxRetries"
                    class="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm"
                  />
                  <p class="text-xs text-slate-500">Cuántas veces reintentar una operación fallida antes de rendirse.</p>
                </div>
             </div>
          </div>

          <!-- ADVANCED TAB -->
          <div v-if="activeTab === 'advanced'" class="p-6 h-full flex flex-col">
             <div class="flex items-center justify-between mb-4">
                <div>
                   <h3 class="text-base font-semibold text-slate-800 font-mono">model_routing.json</h3>
                   <p class="text-sm text-slate-500">Configuración cruda del orquestador. <span class="text-amber-600 font-medium">Uso avanzado.</span></p>
                </div>
                <div v-if="jsonError" class="text-xs text-red-600 font-bold bg-red-50 px-2 py-1 rounded">
                   {{ jsonError }}
                </div>
                <div v-else class="text-xs text-emerald-600 font-bold bg-emerald-50 px-2 py-1 rounded">
                   JSON Válido
                </div>
             </div>
             
             <div class="flex-1 relative min-h-[500px]">
                <textarea
                  v-model="jsonContent"
                  class="absolute inset-0 w-full h-full p-4 bg-slate-900 text-slate-50 font-mono text-xs rounded-xl focus:ring-2 focus:ring-sky-500 outline-none resize-none"
                  spellcheck="false"
                ></textarea>
             </div>
          </div>

        </div>
      </div>
    </main>
  </div>
</template>
