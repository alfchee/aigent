<template>
  <div class="min-h-full bg-bg text-text">
    <ApiKeySetupModal v-if="!apiKeyReady" @saved="apiKeyReady = true" />
    <router-view v-else />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ApiKeySetupModal from '@/components/ApiKeySetupModal.vue'
import { hasApiKey } from '@/services/apiClient'

const apiKeyReady = ref(hasApiKey())
</script>
