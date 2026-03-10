<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { llmApi, type LLMProvider, type LLMModel } from '@/lib/llm'
import LLMProviderCard from '@/components/settings/llm/LLMProviderCard.vue'

const providers = ref<LLMProvider[]>([])
const isLoading = ref(true)
const activeProvider = computed(() => providers.value.find((p) => p.is_active))

// Model Explorer State
const models = ref<LLMModel[]>([])
const isLoadingModels = ref(false)
const showModelExplorer = ref(false)

const loadProviders = async () => {
  isLoading.value = true
  try {
    providers.value = await llmApi.getProviders()

    // Ensure default providers exist if backend returned empty (first run)
    const defaults = ['google', 'openrouter', 'lm_studio']
    defaults.forEach((id) => {
      if (!providers.value.find((p) => p.provider_id === id)) {
        providers.value.push({
          provider_id: id,
          name: id === 'lm_studio' ? 'LM Studio' : id.charAt(0).toUpperCase() + id.slice(1),
          is_active: id === 'google', // Default fallback
          has_key: false,
        })
      }
    })
  } catch (e) {
    console.error('Failed to load providers:', e)
  } finally {
    isLoading.value = false
  }
}

const activateProvider = async (providerId: string) => {
  try {
    await llmApi.activateProvider(providerId)
    // Optimistic update
    providers.value = providers.value.map((p) => ({
      ...p,
      is_active: p.provider_id === providerId,
    }))

    // Refresh models for the new provider
    if (showModelExplorer.value) {
      loadModels(providerId)
    }
  } catch (e) {
    console.error('Failed to activate provider:', e)
    alert('Failed to activate provider')
  }
}

const deactivateProvider = async (providerId: string) => {
  try {
    await llmApi.deactivateProvider(providerId)
    // Optimistic update
    providers.value = providers.value.map((p) => ({
      ...p,
      is_active: false,
    }))

    // Clear models if no provider is active
    if (showModelExplorer.value) {
      models.value = []
    }
  } catch (e) {
    console.error('Failed to deactivate provider:', e)
    alert('Failed to deactivate provider')
  }
}

const updateProvider = (updated: LLMProvider) => {
  const index = providers.value.findIndex((p) => p.provider_id === updated.provider_id)
  if (index !== -1) {
    providers.value[index] = updated
  }
}

const loadModels = async (providerId: string) => {
  if (!providerId) return
  isLoadingModels.value = true
  models.value = []
  try {
    models.value = await llmApi.getProviderModels(providerId)
  } catch (e) {
    console.error('Failed to load models:', e)
  } finally {
    isLoadingModels.value = false
  }
}

const toggleModelExplorer = () => {
  showModelExplorer.value = !showModelExplorer.value
  if (showModelExplorer.value && activeProvider.value) {
    loadModels(activeProvider.value.provider_id)
  }
}

onMounted(() => {
  loadProviders()
})
</script>

<template>
  <div class="max-w-4xl mx-auto space-y-8 pb-12">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-slate-900">LLM Configuration</h1>
      <p class="mt-2 text-slate-600">
        Manage your AI model providers. Switch between Google Gemini, OpenRouter, or local models
        via LM Studio.
      </p>
    </div>

    <!-- Providers List -->
    <div class="space-y-4">
      <div v-if="isLoading" class="flex justify-center py-12">
        <svg
          class="animate-spin h-8 w-8 text-sky-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>
      </div>

      <LLMProviderCard
        v-for="provider in providers"
        v-else
        :key="provider.provider_id"
        :provider="provider"
        @update:provider="updateProvider"
        @activate="activateProvider"
        @deactivate="deactivateProvider"
      />
    </div>

    <!-- Model Explorer Section -->
    <div class="border-t border-slate-200 pt-8">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h2 class="text-lg font-semibold text-slate-900">Model Explorer</h2>
          <p class="text-sm text-slate-500">Discover available models from the active provider.</p>
        </div>
        <button
          class="px-4 py-2 text-sm font-medium text-sky-700 bg-sky-50 rounded-lg hover:bg-sky-100 transition-colors"
          @click="toggleModelExplorer"
        >
          {{ showModelExplorer ? 'Hide Models' : 'Explore Models' }}
        </button>
      </div>

      <div
        v-if="showModelExplorer"
        class="bg-slate-50 rounded-xl p-6 border border-slate-200 animate-in fade-in zoom-in-95 duration-200"
      >
        <div v-if="!activeProvider" class="text-center text-slate-500 py-4">
          No active provider selected.
        </div>

        <div v-else>
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm font-medium text-slate-700">
              Models for <span class="text-sky-600 font-bold">{{ activeProvider.name }}</span>
            </span>
            <button
              class="text-xs text-slate-500 hover:text-sky-600 flex items-center gap-1"
              @click="loadModels(activeProvider.provider_id)"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                ></path>
              </svg>
              Refresh
            </button>
          </div>

          <div v-if="isLoadingModels" class="py-8 text-center">
            <svg
              class="animate-spin h-6 w-6 text-slate-400 mx-auto"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            <p class="mt-2 text-sm text-slate-500">Fetching models...</p>
          </div>

          <div v-else-if="models.length === 0" class="text-center py-8 text-slate-500">
            No models found. Check your API Key or connection.
          </div>

          <div
            v-else
            class="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar"
          >
            <div
              v-for="model in models"
              :key="model.id"
              class="bg-white p-3 rounded-lg border border-slate-200 hover:border-sky-300 hover:shadow-sm transition-all group"
            >
              <div class="font-medium text-slate-800 text-sm truncate" :title="model.id">
                {{ model.display_name }}
              </div>
              <div class="text-xs text-slate-500 mt-1 truncate" :title="model.id">
                {{ model.id }}
              </div>
              <div class="mt-2 flex items-center justify-between">
                <span class="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                  {{
                    model.context_length
                      ? Math.round(model.context_length / 1024) + 'k ctx'
                      : 'Context unknown'
                  }}
                </span>
                <!-- Future: Add "Select Default" button here -->
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
