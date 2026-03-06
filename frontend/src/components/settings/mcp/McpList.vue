<template>
  <div class="space-y-4">
    <!-- Header with Checkbox -->
    <div
      v-if="servers.length > 0"
      class="flex items-center px-4 py-2 bg-slate-50 rounded-lg border border-slate-200"
    >
      <input
        type="checkbox"
        :checked="allSelected"
        @change="$emit('toggle-all', ($event.target as HTMLInputElement).checked)"
        class="w-4 h-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500"
      />
      <span class="ml-3 text-xs font-semibold text-slate-500 uppercase tracking-wider"
        >Servidores ({{ servers.length }})</span
      >
    </div>

    <div
      v-if="servers.length === 0"
      class="text-center py-8 text-slate-500 bg-slate-50 rounded-xl border border-dashed border-slate-300"
    >
      No hay servidores MCP configurados.
    </div>

    <div
      v-for="server in servers"
      :key="server.id"
      class="bg-white border border-slate-200 rounded-xl p-4 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow"
    >
      <div class="flex items-center gap-4">
        <input
          type="checkbox"
          :checked="selectedIds.includes(server.id)"
          @change="$emit('toggle-select', server.id)"
          class="w-4 h-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500"
        />

        <div class="p-3 bg-sky-50 text-sky-600 rounded-lg">
          <!-- Icon placeholder -->
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
            ></path>
          </svg>
        </div>
        <div>
          <h4 class="font-medium text-slate-900">{{ server.name }}</h4>
          <div class="flex items-center gap-2 text-xs text-slate-500">
            <span class="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-mono">{{
              server.type
            }}</span>
            <span v-if="server.enabled" class="text-emerald-600 flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Activo
            </span>
            <span v-else class="text-slate-400 flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Deshabilitado
            </span>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <!-- Toggle Switch -->
        <button
          @click="$emit('toggle', server)"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
          :class="server.enabled ? 'bg-sky-600' : 'bg-slate-200'"
        >
          <span
            class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
            :class="server.enabled ? 'translate-x-6' : 'translate-x-1'"
          />
        </button>

        <div class="h-6 w-px bg-slate-200 mx-2"></div>

        <button
          @click="$emit('edit', server)"
          class="p-2 text-slate-400 hover:text-sky-600 hover:bg-sky-50 rounded-lg transition-colors"
          title="Editar"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            ></path>
          </svg>
        </button>
        <button
          @click="$emit('delete', server)"
          class="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          title="Eliminar"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            ></path>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps, defineEmits, computed } from 'vue'

const props = defineProps<{
  servers: any[]
  selectedIds: string[]
}>()

defineEmits(['edit', 'delete', 'toggle', 'toggle-select', 'toggle-all'])

const allSelected = computed(() => {
  return props.servers.length > 0 && props.servers.every((s) => props.selectedIds.includes(s.id))
})
</script>
