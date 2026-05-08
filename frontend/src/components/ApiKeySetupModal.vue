<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
  >
    <div class="w-full max-w-md rounded-xl bg-bg-surface p-8 shadow-2xl">
      <h2 class="mb-2 text-xl font-semibold text-text">API Key Required</h2>
      <p class="mb-6 text-sm text-text-muted">
        Enter your
        <code class="rounded bg-bg px-1 py-0.5 font-mono text-xs">AIGENT_API_KEY</code> to
        access this app. The key is stored only in your browser's local storage.
      </p>

      <form @submit.prevent="submit">
        <label class="mb-1 block text-xs font-medium text-text-muted" for="api-key-input">
          API Key
        </label>
        <input
          id="api-key-input"
          v-model="keyInput"
          type="password"
          autocomplete="current-password"
          placeholder="your-secret-key"
          class="mb-4 w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <p v-if="error" class="mb-3 text-xs text-red-400">{{ error }}</p>
        <button
          type="submit"
          class="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          Save & Continue
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { setStoredApiKey } from '@/services/apiClient'

const emit = defineEmits<{ (e: 'saved'): void }>()

const keyInput = ref('')
const error = ref('')

function submit() {
  const trimmed = keyInput.value.trim()
  if (!trimmed) {
    error.value = 'Please enter a valid API key.'
    return
  }
  setStoredApiKey(trimmed)
  emit('saved')
}
</script>
