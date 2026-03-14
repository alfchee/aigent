<script setup lang="ts">
import { ref, computed } from 'vue'
import type { LLMProvider } from '@/lib/llm'
import { llmApi } from '@/lib/llm'

const props = defineProps<{
  provider: LLMProvider
}>()

const emit = defineEmits<{
  (e: 'update:provider', provider: LLMProvider): void
  (e: 'activate', providerId: string): void
  (e: 'deactivate', providerId: string): void
}>()

const isEditing = ref(false)
const apiKey = ref('')
const baseUrl = ref(props.provider.base_url || '')
const isSaving = ref(false)
const showKey = ref(false)

const isActive = computed(() => props.provider.is_active)

const toggleActive = async () => {
  if (isActive.value) {
    emit('deactivate', props.provider.provider_id)
  } else {
    emit('activate', props.provider.provider_id)
  }
}

const saveConfig = async () => {
  isSaving.value = true
  try {
    await llmApi.saveProvider({
      provider_id: props.provider.provider_id,
      name: props.provider.name,
      api_key: apiKey.value || undefined,
      base_url: baseUrl.value || undefined,
    })

    // Refresh local state or emit update
    // Ideally parent re-fetches, but we can simulate update
    const updated = { ...props.provider }
    if (apiKey.value) updated.has_key = true
    if (baseUrl.value) updated.base_url = baseUrl.value

    emit('update:provider', updated)
    isEditing.value = false
    apiKey.value = '' // Clear for security
  } catch (e) {
    console.error('Error saving provider:', e)
    alert('Error saving configuration')
  } finally {
    isSaving.value = false
  }
}

const startEditing = () => {
  isEditing.value = true
  baseUrl.value = props.provider.base_url || ''
  apiKey.value = '' // Don't show existing key
}

const cancelEditing = () => {
  isEditing.value = false
  apiKey.value = ''
}
</script>

<template>
  <div
    class="bg-white border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-all"
  >
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-4">
        <!-- Icon -->
        <div
          class="p-3 rounded-lg"
          :class="isActive ? 'bg-sky-50 text-sky-600' : 'bg-slate-50 text-slate-400'"
        >
          <svg
            v-if="provider.provider_id === 'google'"
            class="w-8 h-8"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path
              d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .533 5.347.533 12S5.867 24 12.48 24c3.44 0 6.053-1.147 8.16-2.933 2.16-1.787 2.827-4.56 2.827-6.853 0-.667-.08-1.307-.213-1.92h-10.773z"
            />
          </svg>
          <svg
            v-else-if="provider.provider_id === 'openrouter'"
            class="w-8 h-8"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <svg
            v-else
            class="w-8 h-8"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </div>

        <div>
          <h3 class="text-lg font-semibold text-slate-900">{{ provider.name }}</h3>
          <div class="flex items-center gap-2 mt-1">
            <span
              v-if="isActive"
              class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Active
            </span>
            <span
              v-else
              class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600"
            >
              Inactive
            </span>

            <span
              v-if="provider.has_key"
              class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-sky-50 text-sky-700 border border-sky-100"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
                ></path>
              </svg>
              Configured
            </span>
            <span
              v-else
              class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-100"
            >
              Missing Key
            </span>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button
          class="px-4 py-2 text-sm font-medium transition-colors border rounded-lg"
          :class="
            isActive
              ? 'text-red-600 bg-white border-red-200 hover:bg-red-50'
              : 'text-slate-600 bg-white border-slate-300 hover:bg-slate-50 hover:text-sky-600'
          "
          @click="toggleActive"
        >
          {{ isActive ? 'Deactivate' : 'Activate' }}
        </button>

        <button
          class="p-2 text-slate-400 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-colors"
          @click="isEditing ? cancelEditing() : startEditing()"
        >
          <svg
            v-if="!isEditing"
            class="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            ></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            ></path>
          </svg>
        </button>
      </div>
    </div>

    <!-- Configuration Form -->
    <div
      v-if="isEditing"
      class="mt-6 pt-6 border-t border-slate-100 animate-in slide-in-from-top-2"
    >
      <div class="space-y-4">
        <!-- API Key Input -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">
            API Key
            <span v-if="provider.has_key" class="text-xs text-emerald-600 font-normal"
              >(Stored securely)</span
            >
          </label>
          <div class="relative">
            <input
              v-model="apiKey"
              :type="showKey ? 'text' : 'password'"
              :placeholder="
                provider.has_key
                  ? '•••••••••••••••• (Leave empty to keep unchanged)'
                  : 'Enter API Key'
              "
              class="w-full pl-4 pr-10 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all"
            />
            <button
              class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              @click="showKey = !showKey"
            >
              <svg
                v-if="showKey"
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                ></path>
              </svg>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                ></path>
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                ></path>
              </svg>
            </button>
          </div>
          <p v-if="provider.provider_id === 'openrouter'" class="mt-1 text-xs text-slate-500">
            Get your API key from
            <a
              href="https://openrouter.ai/keys"
              target="_blank"
              class="text-sky-600 hover:underline"
              >openrouter.ai</a
            >
          </p>
          <p v-if="provider.provider_id === 'google'" class="mt-1 text-xs text-slate-500">
            Get your API key from
            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              class="text-sky-600 hover:underline"
              >Google AI Studio</a
            >
          </p>
        </div>

        <!-- Base URL Input -->
        <div v-if="provider.provider_id !== 'google'">
          <label class="block text-sm font-medium text-slate-700 mb-1">Base URL</label>
          <input
            v-model="baseUrl"
            type="text"
            placeholder="https://api.example.com/v1"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all"
          />
          <p class="mt-1 text-xs text-slate-500">
            Optional. Use for local proxies or custom endpoints.
          </p>
        </div>

        <!-- Action Buttons -->
        <div class="flex items-center justify-end gap-3 mt-6">
          <button
            class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
            @click="cancelEditing"
          >
            Cancel
          </button>
          <button
            :disabled="isSaving"
            class="px-4 py-2 text-sm font-medium text-white bg-sky-600 rounded-lg hover:bg-sky-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            @click="saveConfig"
          >
            <svg
              v-if="isSaving"
              class="animate-spin h-4 w-4 text-white"
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
            {{ isSaving ? 'Saving...' : 'Save Configuration' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
