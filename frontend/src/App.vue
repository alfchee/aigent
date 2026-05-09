<template>
  <div class="min-h-full bg-bg text-text">
    <ApiKeySetupModal v-if="showSetup" @saved="showSetup = false" />
    <router-view v-else />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ApiKeySetupModal from '@/components/ApiKeySetupModal.vue'
import { hasApiKey } from '@/services/apiClient'

// Only block the UI when auth is explicitly enabled AND no key is stored yet.
// When VITE_AUTH_ENABLED is not set (dev default), the modal never appears.
const authEnabled = import.meta.env.VITE_AUTH_ENABLED === 'true'
const showSetup = ref(authEnabled && !hasApiKey())
</script>
