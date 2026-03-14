<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useProviderStore } from '../stores/providers'

const providerStore = useProviderStore()

const providers = computed(() => providerStore.availableProviders)
const selectedProvider = computed({
  get: () => providerStore.selectedProvider,
  set: (value: string) => providerStore.setProvider(value),
})

const hasMultipleProviders = computed(() => providers.value.length > 1)

onMounted(async () => {
  providerStore.loadFromStorage()
  await providerStore.loadProviders()
})

function handleChange(event: Event) {
  const target = event.target as HTMLSelectElement
  providerStore.setProvider(target.value || '')
}
</script>

<template>
  <div v-if="hasMultipleProviders" class="px-3 py-2 border-b border-slate-200">
    <label class="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
      Provider
    </label>
    <select
      v-model="selectedProvider"
      class="w-full appearance-none pl-3 pr-8 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors text-xs font-medium text-slate-700 bg-white cursor-pointer focus:outline-none focus:ring-2 focus:ring-sky-500/20"
      @change="handleChange"
    >
      <option value="">Default</option>
      <option
        v-for="provider in providers"
        :key="provider.provider_id"
        :value="provider.provider_id"
      >
        {{ provider.name }}
      </option>
    </select>
    <span
      class="material-icons-outlined text-xs text-slate-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none"
      style="margin-top: 8px"
    >
      expand_more
    </span>
  </div>
</template>
