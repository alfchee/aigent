<template>
  <div v-if="show" class="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
      <div class="p-6 border-b border-slate-100 flex justify-between items-center">
        <h3 class="text-lg font-semibold text-slate-800">
          {{ isEdit ? 'Editar Servidor MCP' : 'Nuevo Servidor MCP' }}
        </h3>
        <button @click="$emit('close')" class="text-slate-400 hover:text-slate-600">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            ></path>
          </svg>
        </button>
      </div>

      <div class="p-6 space-y-6">
        <!-- Type Selection -->
        <div v-if="!isEdit" class="space-y-2">
          <label class="block text-sm font-medium text-slate-700">Tipo de Servidor</label>
          <select
            v-model="form.id"
            @change="onTypeChange"
            class="w-full p-2 border border-slate-200 rounded-lg"
          >
            <option value="" disabled>Selecciona un tipo...</option>
            <option value="__custom__">Servidor personalizado</option>
            <option v-for="(def, key) in marketplace" :key="key" :value="key">
              {{ def.name }}
            </option>
          </select>
          <p v-if="activeDef" class="text-sm text-slate-500">{{ activeDef.description }}</p>
        </div>
        <div v-else class="space-y-2">
          <label class="block text-sm font-medium text-slate-700">Servidor</label>
          <div class="text-slate-900 font-medium">{{ form.name || form.id }}</div>
        </div>

        <div v-if="isCustomDefinition" class="space-y-4">
          <div class="space-y-1">
            <label class="block text-sm font-medium text-slate-700">ID del servidor</label>
            <input
              v-model="form.customId"
              type="text"
              :disabled="!isCustomMode"
              class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none disabled:bg-slate-100"
              placeholder="mi-servidor"
            />
          </div>
          <div class="space-y-1">
            <label class="block text-sm font-medium text-slate-700">Nombre</label>
            <input
              v-model="form.name"
              type="text"
              class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
              placeholder="Servidor MCP personalizado"
            />
          </div>
          <div class="space-y-1">
            <label class="block text-sm font-medium text-slate-700">Descripción</label>
            <textarea
              v-model="form.description"
              class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
              rows="2"
            ></textarea>
          </div>
          <div class="space-y-1">
            <label class="block text-sm font-medium text-slate-700">Comando</label>
            <input
              v-model="form.command"
              type="text"
              class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
              placeholder="npx"
            />
          </div>
          <div class="space-y-1">
            <label class="block text-sm font-medium text-slate-700">Argumentos</label>
            <input
              v-model="form.argsText"
              type="text"
              class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
              placeholder="-y @mcp/server {param}"
            />
          </div>
          <div class="space-y-1">
            <label class="block text-sm font-medium text-slate-700">Parámetros requeridos</label>
            <input
              v-model="form.paramsList"
              type="text"
              class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
              placeholder="path, connection_string"
            />
          </div>
          <div class="space-y-1">
            <label class="block text-sm font-medium text-slate-700"
              >Variables de entorno requeridas</label
            >
            <input
              v-model="form.envVarsList"
              type="text"
              class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
              placeholder="GITHUB_TOKEN, SLACK_TOKEN"
            />
          </div>
        </div>

        <div v-if="activeDef" class="space-y-6">
          <div v-if="activeDef.params && activeDef.params.length > 0" class="space-y-4">
            <h4 class="text-sm font-semibold text-slate-900 border-b pb-2">
              Parámetros de Configuración
            </h4>
            <div v-for="param in activeDef.params" :key="param" class="space-y-1">
              <label class="block text-sm font-medium text-slate-700">{{ param }}</label>
              <input
                v-model="form.params[param]"
                type="text"
                class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
                :placeholder="`Valor para ${param}`"
              />
            </div>
          </div>

          <div v-if="activeDef.env_vars && activeDef.env_vars.length > 0" class="space-y-4">
            <h4 class="text-sm font-semibold text-slate-900 border-b pb-2">
              Variables de Entorno (Credenciales)
            </h4>
            <div v-for="env in activeDef.env_vars" :key="env" class="space-y-1">
              <label class="block text-sm font-medium text-slate-700">{{ env }}</label>
              <input
                v-model="form.env_vars[env]"
                type="password"
                class="w-full p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div class="flex items-center gap-2">
            <input
              type="checkbox"
              v-model="form.enabled"
              id="enabled"
              class="w-4 h-4 text-sky-600 rounded"
            />
            <label for="enabled" class="text-sm font-medium text-slate-700"
              >Habilitar este servidor</label
            >
          </div>
        </div>
      </div>

      <div
        class="p-6 bg-slate-50 border-t border-slate-100 flex justify-between items-center rounded-b-xl"
      >
        <button
          @click="testConnection"
          :disabled="testing || !form.id"
          class="px-4 py-2 text-sm font-medium text-sky-700 bg-sky-100 hover:bg-sky-200 rounded-lg transition-colors disabled:opacity-50"
        >
          {{ testing ? 'Probando...' : 'Probar Conexión' }}
        </button>

        <div class="flex gap-3">
          <button
            @click="$emit('close')"
            class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800"
          >
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
  customId: '',
  name: '',
  description: '',
  command: '',
  argsText: '',
  paramsList: '',
  envVarsList: '',
  enabled: true,
  params: {} as Record<string, any>,
  env_vars: {} as Record<string, string>,
})

const testing = ref(false)

const isEdit = computed(() => !!props.server)
const marketplace = computed(() => store.marketplace)
const selectedDef = computed(() => (form.value.id ? marketplace.value[form.value.id] : null))
const isCustomMode = computed(() => form.value.id === '__custom__')
const isCustomDefinition = computed(() => {
  if (isCustomMode.value) return true
  return selectedDef.value?.source === 'custom'
})
const activeDef = computed(() => {
  if (!isCustomDefinition.value) return selectedDef.value || null
  const params = parseList(form.value.paramsList)
  const envVars = parseList(form.value.envVarsList)
  const args = parseList(form.value.argsText)
  return {
    name: form.value.name || 'Servidor MCP',
    description: form.value.description || '',
    command: form.value.command || '',
    args: args,
    params: params,
    env_vars: envVars,
    source: 'custom',
  }
})

watch(
  () => props.server,
  (newVal) => {
    if (newVal) {
      form.value = JSON.parse(JSON.stringify(newVal))
      if (!form.value.params) form.value.params = {}
      if (!form.value.env_vars) form.value.env_vars = {}
      form.value.customId = newVal.id
      const def = selectedDef.value
      if (def?.source === 'custom') {
        form.value.name = def.name || form.value.name
        form.value.description = def.description || ''
        form.value.command = def.command || ''
        form.value.argsText = (def.args || []).join(', ')
        form.value.paramsList = (def.params || []).join(', ')
        form.value.envVarsList = (def.env_vars || []).join(', ')
      }
    } else {
      resetForm()
    }
  },
  { immediate: true },
)

watch(
  () => selectedDef.value,
  (def) => {
    if (!def || def.source !== 'custom' || isCustomMode.value) return
    if (!form.value.name) form.value.name = def.name || form.value.name
    if (!form.value.description) form.value.description = def.description || ''
    if (!form.value.command) form.value.command = def.command || ''
    if (!form.value.argsText) form.value.argsText = (def.args || []).join(', ')
    if (!form.value.paramsList) form.value.paramsList = (def.params || []).join(', ')
    if (!form.value.envVarsList) form.value.envVarsList = (def.env_vars || []).join(', ')
  },
)

watch(
  () => activeDef.value?.env_vars,
  (envVars) => {
    if (!envVars) return
    for (const env of envVars) {
      if (!(env in form.value.env_vars)) {
        form.value.env_vars[env] = ''
      }
    }
  },
  { deep: true, immediate: true },
)

function resetForm() {
  form.value = {
    id: '',
    customId: '',
    name: '',
    description: '',
    command: '',
    argsText: '',
    paramsList: '',
    envVarsList: '',
    enabled: true,
    params: {},
    env_vars: {},
  }
}

function onTypeChange() {
  form.value.params = {}
  form.value.env_vars = {}
  if (isCustomMode.value) {
    form.value.customId = ''
    form.value.name = ''
    form.value.description = ''
    form.value.command = ''
    form.value.argsText = ''
    form.value.paramsList = ''
    form.value.envVarsList = ''
  }
}

const isValid = computed(() => {
  if (isCustomMode.value) {
    if (!form.value.customId || !form.value.command) return false
  } else if (!form.value.id) {
    return false
  }
  return true
})

async function testConnection() {
  testing.value = true
  const payload = buildPayload()
  const res = await store.testConnection(
    payload.server_id,
    payload.params,
    payload.env_vars,
    payload.definition,
  )
  testing.value = false
  alert(res.message) // Replace with better notification
}

function save() {
  emit('save', buildPayload())
}

function parseList(value: string) {
  if (!value) return []
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function buildPayload() {
  const serverId = isCustomMode.value ? form.value.customId.trim() : form.value.id
  const definition = isCustomDefinition.value
    ? {
        server_id: serverId,
        name: form.value.name || serverId,
        description: form.value.description || '',
        command: form.value.command,
        args: parseList(form.value.argsText),
        params: parseList(form.value.paramsList),
        env_vars: parseList(form.value.envVarsList),
      }
    : undefined
  return {
    server_id: serverId,
    enabled: form.value.enabled,
    params: form.value.params,
    env_vars: form.value.env_vars,
    definition,
  }
}
</script>
