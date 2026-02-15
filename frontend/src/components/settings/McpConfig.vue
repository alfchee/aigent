<template>
  <div class="p-6 space-y-8">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-base font-semibold text-slate-800 flex items-center gap-2">
          <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
          Configuración MCP
        </h3>
        <p class="text-sm text-slate-500 mt-1">Gestiona tus servidores del Protocolo de Contexto de Modelos (MCP).</p>
      </div>
      <div class="flex gap-2">
         <div v-if="selectedIds.length > 0" class="flex items-center gap-2 bg-slate-100 p-1 rounded-lg">
             <span class="text-xs font-medium text-slate-600 px-2">{{ selectedIds.length }} seleccionados</span>
             <button @click="bulkDelete" class="p-1.5 text-red-600 hover:bg-red-100 rounded-md transition-colors" title="Eliminar seleccionados">
                 <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
             </button>
         </div>
         <button 
            @click="openModal()"
            class="flex items-center gap-2 px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700 transition-colors text-sm font-medium"
         >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            Añadir MCP
         </button>
      </div>
    </div>

    <div class="bg-white border border-slate-200 rounded-xl p-4">
        <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div class="space-y-1">
                <div class="text-sm font-semibold text-slate-800">Importar marketplace</div>
                <div class="text-xs text-slate-500">Agrega una URL pública con definiciones MCP.</div>
            </div>
            <div class="flex flex-col gap-2 md:flex-row md:items-center md:w-2/3">
                <input
                    v-model="importUrl"
                    type="text"
                    class="w-full md:flex-1 p-2.5 border border-slate-200 rounded-lg text-sm"
                    placeholder="https://ejemplo.com/mcp_registry.json"
                />
                <button
                    @click="importMarketplace"
                    :disabled="!importUrl || importLoading"
                    class="px-4 py-2 text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 rounded-lg disabled:opacity-50"
                >
                    {{ importLoading ? 'Importando…' : 'Importar' }}
                </button>
            </div>
        </div>
        <div v-if="importError" class="mt-3 text-xs text-red-600">{{ importError }}</div>
    </div>

    <div v-if="store.loading && !store.servers.length" class="text-center py-12">
        <div class="animate-spin h-8 w-8 border-4 border-sky-500 border-t-transparent rounded-full mx-auto mb-2"></div>
        <p class="text-slate-500">Cargando servidores...</p>
    </div>
    
    <div v-else>
        <div v-if="store.error" class="mb-4 p-4 bg-red-50 text-red-600 rounded-lg border border-red-200 flex justify-between items-center">
            <span>{{ store.error }}</span>
            <button @click="store.error = null" class="text-red-800 hover:text-red-900">&times;</button>
        </div>

        <McpList 
            :servers="store.servers" 
            :selectedIds="selectedIds"
            @edit="openModal" 
            @delete="confirmDelete"
            @toggle="toggleServer"
            @toggle-select="toggleSelection"
            @toggle-all="toggleAll"
        />
    </div>

    <McpServerModal 
        :show="showModal"
        :server="editingServer"
        @close="showModal = false"
        @save="handleSave"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onErrorCaptured } from 'vue'
import { useMcpStore, type McpServer } from '../../stores/mcpStore'
import McpList from './mcp/McpList.vue'
import McpServerModal from './mcp/McpServerModal.vue'

const store = useMcpStore()
const showModal = ref(false)
const editingServer = ref<McpServer | undefined>(undefined)
const selectedIds = ref<string[]>([])
const importUrl = ref('')
const importLoading = ref(false)
const importError = ref<string | null>(null)

// Error Boundary
onErrorCaptured((err) => {
    console.error('McpConfig Error Boundary:', err)
    store.error = 'Ocurrió un error inesperado en la interfaz. Por favor recarga la página.'
    return false // Prevent propagation
})

onMounted(() => {
    store.fetchServers()
    store.fetchMarketplace()
})

function openModal(server?: McpServer) {
    editingServer.value = server
    showModal.value = true
}

async function handleSave(serverData: Partial<McpServer>) {
    try {
        await store.saveServer(serverData)
        showModal.value = false
    } catch (e) {
        // Error handled in store
    }
}

async function confirmDelete(server: McpServer) {
    if (confirm(`¿Estás seguro de eliminar la configuración para ${server.name}?`)) {
        await store.deleteServer(server.id)
    }
}

async function toggleServer(server: McpServer) {
    try {
        await store.saveServer({
            ...server,
            server_id: server.id, // Ensure ID is passed
            enabled: !server.enabled
        })
    } catch (e: any) {
        store.error = e.message || 'Error al cambiar estado del servidor'
    }
}

function toggleSelection(id: string) {
    if (selectedIds.value.includes(id)) {
        selectedIds.value = selectedIds.value.filter(i => i !== id)
    } else {
        selectedIds.value.push(id)
    }
}

function toggleAll(checked: boolean) {
    if (checked) {
        selectedIds.value = store.servers.map(s => s.id)
    } else {
        selectedIds.value = []
    }
}

async function bulkDelete() {
    if (!confirm(`¿Eliminar ${selectedIds.value.length} servidores?`)) return
    
    // Execute deletions in parallel
    await Promise.all(selectedIds.value.map(id => store.deleteServer(id)))
    selectedIds.value = []
}

async function importMarketplace() {
    if (!importUrl.value.trim()) return
    importLoading.value = true
    importError.value = null
    try {
        await store.importMarketplace(importUrl.value.trim())
        importUrl.value = ''
    } catch (e: any) {
        importError.value = e.message || 'Error importando marketplace'
    } finally {
        importLoading.value = false
    }
}
</script>
