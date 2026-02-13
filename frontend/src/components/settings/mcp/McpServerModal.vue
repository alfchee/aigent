<template>
  <div v-if="show" class="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
      <div class="p-6 border-b border-slate-100 flex justify-between items-center">
        <h3 class="text-lg font-semibold text-slate-800">
          {{ isEdit ? 'Editar Servidor MCP' : 'Nuevo Servidor MCP' }}
        </h3>
        <button @click="$emit('close')" class="text-slate-400 hover:text-slate-600">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
      </div>
      
      <div class="p-6 space-y-6">
        <!-- Type Selection -->
        <div v-if="!isEdit" class="space-y-2">
          <label class="block text-sm font-medium text-slate-700">Tipo de Servidor</label>
          <select v-model="form.id" @change="onTypeChange" class="w-full p-2 border border-slate-200 rounded-lg">
            <option value="" disabled>Selecciona un tipo...</option>
            <option v-for="(def, key) in marketplace" :key="key" :value="key">
              {{ def.name }}
            </option>
          </select>
          <p v-if="selectedDef" class="text-sm text-slate-500">{{ selectedDef.description }}</p>
        </div>
        <div v-else class="space-y-2">
           <label class="block text-sm font-medium text-slate-700">Servidor</label>
           <div class="text-slate-900 font-medium">{{ form.name || form.id }}</div>
        </div>

        <div v-if="selectedDef" class="space-y-6">
            <!-- Params -->
            <div v-if="selectedDef.params && selectedDef.params.length > 0" class="space-y-4">
                <h4 class="text-sm font-semibold text-slate-900 border-b pb-2">Parámetros de Configuración</h4>
                <div v-for="param in selectedDef.params" :key="param" class="space-y-1">
                    <label class="block text-sm font-medium text-slate-700">{{ param }}</label>
                    <input 
                        v-model="form.params[param]" 
                        type="text" 
                        class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
                        :placeholder="`Valor para ${param}`"
                    >
                </div>
            </div>

            <!-- Env Vars -->
            <div v-if="selectedDef.env_vars && selectedDef.env_vars.length > 0" class="space-y-4">
                <h4 class="text-sm font-semibold text-slate-900 border-b pb-2">Variables de Entorno (Credenciales)</h4>
                <div v-for="env in selectedDef.env_vars" :key="env" class="space-y-1">
                    <label class="block text-sm font-medium text-slate-700">{{ env }}</label>
                    <input 
                        v-model="form.env_vars[env]" 
                        type="password" 
                        class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
                        placeholder="••••••••"
                    >
                </div>
            </div>

            <!-- Enabled -->
            <div class="flex items-center gap-2">
                <input type="checkbox" v-model="form.enabled" id="enabled" class="w-4 h-4 text-sky-600 rounded">
                <label for="enabled" class="text-sm font-medium text-slate-700">Habilitar este servidor</label>
            </div>
        </div>
      </div>

      <div class="p-6 bg-slate-50 border-t border-slate-100 flex justify-between items-center rounded-b-xl">
        <button 
            @click="testConnection" 
            :disabled="testing || !form.id"
            class="px-4 py-2 text-sm font-medium text-sky-700 bg-sky-100 hover:bg-sky-200 rounded-lg transition-colors disabled:opacity-50"
        >
            {{ testing ? 'Probando...' : 'Probar Conexión' }}
        </button>

        <div class="flex gap-3">
            <button @click="$emit('close')" class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800">
                Cancelar
            </button>
            <button 
                @click="save" 
                :disabled="!isValid"
                class="px-4 py-2 text-sm font-medium text-white bg-sky-600 hover:bg-sky-700 rounded-lg shadow-sm disabled:opacity-50"
            >
                Guardar
            </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMcpStore } from '../../../stores/mcpStore'

const props = defineProps<{
  show: boolean
  server?: any
}>()

const emit = defineEmits(['close', 'save'])
const store = useMcpStore()

const form = ref({
    id: '',
    name: '',
    enabled: true,
    params: {} as Record<string, any>,
    env_vars: {} as Record<string, string>
})

const testing = ref(false)

const isEdit = computed(() => !!props.server)
const marketplace = computed(() => store.marketplace)
const selectedDef = computed(() => form.value.id ? marketplace.value[form.value.id] : null)

watch(() => props.server, (newVal) => {
    if (newVal) {
        form.value = JSON.parse(JSON.stringify(newVal))
        // Ensure params/env_vars exist
        if (!form.value.params) form.value.params = {}
        if (!form.value.env_vars) form.value.env_vars = {}
    } else {
        resetForm()
    }
}, { immediate: true })

function resetForm() {
    form.value = {
        id: '',
        name: '',
        enabled: true,
        params: {},
        env_vars: {}
    }
}

function onTypeChange() {
    // Reset params/env_vars when type changes
    form.value.params = {}
    form.value.env_vars = {}
}

const isValid = computed(() => {
    if (!form.value.id) return false
    // Basic validation: check if required params are filled?
    // For now, let's assume if ID is set, it's valid enough to try save
    return true
})

async function testConnection() {
    testing.value = true
    const res = await store.testConnection(form.value.id, form.value.params, form.value.env_vars)
    testing.value = false
    alert(res.message) // Replace with better notification
}

function save() {
    emit('save', {
        server_id: form.value.id,
        ...form.value
    })
}
</script>
