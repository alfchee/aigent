<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useChannelsStore } from '../stores/channels'

const store = useChannelsStore()
const localSettings = reactive<Record<string, Record<string, any>>>({})

const channels = computed(() => store.channels)

function syncLocalSettings() {
  channels.value.forEach((channel) => {
    if (!localSettings[channel.channel_id]) {
      localSettings[channel.channel_id] = { ...(channel.settings || {}) }
    }
  })
}

async function load() {
  await store.loadChannels()
  syncLocalSettings()
  store.connectSse()
}

function updateField(channelId: string, key: string, value: any) {
  if (!localSettings[channelId]) {
    localSettings[channelId] = {}
  }
  localSettings[channelId][key] = value
}

function getFieldValue(channelId: string, key: string) {
  return localSettings[channelId]?.[key] ?? ''
}

async function validateChannel(channelId: string) {
  const settings = localSettings[channelId] || {}
  await store.validateChannel(channelId, settings, true)
}

async function enableChannel(channelId: string) {
  const settings = localSettings[channelId] || {}
  await store.enableChannel(channelId, settings)
}

async function disableChannel(channelId: string) {
  await store.disableChannel(channelId)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
    <header
      class="p-4 bg-white border-b border-slate-200 flex items-center justify-between shadow-sm sticky top-0 z-10"
    >
      <div class="flex items-center gap-3">
        <RouterLink
          to="/"
          class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50"
          target="_blank"
          rel="noopener noreferrer"
        >
          Volver
        </RouterLink>
        <div class="text-sm font-semibold text-slate-800">Channel Manager</div>
      </div>
      <RouterLink
        to="/settings"
        class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50"
      >
        Configuración
      </RouterLink>
    </header>

    <main class="flex-1 p-6 space-y-6">
      <div
        v-if="store.error"
        class="bg-rose-50 text-rose-700 border border-rose-200 rounded p-3 text-sm"
      >
        {{ store.error }}
      </div>

      <div v-if="store.loading" class="text-sm text-slate-500">Cargando canales…</div>

      <div
        v-for="channel in channels"
        :key="channel.channel_id"
        class="bg-white border border-slate-200 rounded-lg shadow-sm p-4 space-y-4"
      >
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="text-lg font-semibold text-slate-900">{{ channel.display_name }}</div>
            <div class="text-xs text-slate-500">
              {{ channel.channel_id }} · v{{ channel.version }}
            </div>
            <div class="text-xs text-slate-500">
              Estado:
              <span
                class="font-medium"
                :class="
                  channel.status?.state === 'active'
                    ? 'text-emerald-600'
                    : channel.status?.state === 'error'
                      ? 'text-rose-600'
                      : 'text-slate-600'
                "
              >
                {{ channel.status?.state || (channel.enabled ? 'pending' : 'disabled') }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="text-xs px-3 py-1.5 rounded border border-slate-200 hover:bg-slate-50"
              type="button"
              @click="validateChannel(channel.channel_id)"
            >
              Validar
            </button>
            <button
              v-if="!channel.enabled"
              class="text-xs px-3 py-1.5 rounded bg-sky-500 text-white hover:bg-sky-600"
              type="button"
              @click="enableChannel(channel.channel_id)"
            >
              Habilitar
            </button>
            <button
              v-else
              class="text-xs px-3 py-1.5 rounded bg-slate-700 text-white hover:bg-slate-800"
              type="button"
              @click="disableChannel(channel.channel_id)"
            >
              Deshabilitar
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            v-for="field in channel.settings_schema?.fields || []"
            :key="field.key"
            class="flex flex-col gap-1"
          >
            <label class="text-xs text-slate-600">{{ field.label }}</label>
            <input
              v-if="field.type === 'secret'"
              type="password"
              class="border border-slate-200 rounded px-3 py-2 text-sm"
              :value="getFieldValue(channel.channel_id, field.key)"
              @input="
                updateField(
                  channel.channel_id,
                  field.key,
                  ($event.target as HTMLInputElement).value,
                )
              "
            />
            <input
              v-else-if="field.type === 'boolean'"
              type="checkbox"
              class="h-4 w-4"
              :checked="Boolean(getFieldValue(channel.channel_id, field.key))"
              @change="
                updateField(
                  channel.channel_id,
                  field.key,
                  ($event.target as HTMLInputElement).checked,
                )
              "
            />
            <input
              v-else
              type="text"
              class="border border-slate-200 rounded px-3 py-2 text-sm"
              :value="getFieldValue(channel.channel_id, field.key)"
              @input="
                updateField(
                  channel.channel_id,
                  field.key,
                  ($event.target as HTMLInputElement).value,
                )
              "
            />
          </div>
        </div>

        <div
          v-if="store.validationErrors[channel.channel_id]?.length"
          class="text-xs text-rose-600"
        >
          <div v-for="err in store.validationErrors[channel.channel_id]" :key="err">{{ err }}</div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-600">
          <div>Último heartbeat: {{ channel.status?.last_heartbeat || '—' }}</div>
          <div>Último error: {{ channel.status?.last_error || '—' }}</div>
          <div>Eventos/min: {{ channel.status?.event_rate ?? 0 }}</div>
        </div>
      </div>
    </main>
  </div>
</template>
