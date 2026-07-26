<template>
  <div class="min-h-full bg-bg text-text">
    <ApiKeySetupModal v-if="showSetup" @saved="onSaved" />
    <router-view v-else />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import ApiKeySetupModal from '@/components/ApiKeySetupModal.vue'
import { hasApiKey, onAuthFailure } from '@/services/apiClient'

// Block the UI when auth is explicitly enabled AND no key is stored yet. When
// VITE_AUTH_ENABLED is not set (dev default) the modal never appears on load.
// A 401 from the backend (key missing/wrong/rotated) re-opens the modal so the
// UI self-heals regardless of the VITE_AUTH_ENABLED flag.
const authEnabled = import.meta.env.VITE_AUTH_ENABLED === 'true'
const showSetup = ref(authEnabled && !hasApiKey())

let unsubAuthFailure: (() => void) | null = null

function onSaved() {
  showSetup.value = false
}

onMounted(() => {
  unsubAuthFailure = onAuthFailure(() => {
    showSetup.value = true
  })
})

onUnmounted(() => {
  unsubAuthFailure?.()
})
</script>
