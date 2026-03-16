<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from '@/components/ui/Button.vue'
import Toggle from '@/components/ui/Toggle.vue'
import TextField from '@/components/ui/TextField.vue'
import { usePreferencesStore } from '@/stores/preferences'
import { useUserConfigStore } from '@/stores/userConfig'
import { useWebSocketStore } from '@/stores/websocket'
import { downloadText } from '@/services/exportChat'
import { listConversations } from '@/services/storage'

const router = useRouter()
const prefs = usePreferencesStore()
const user = useUserConfigStore()
const ws = useWebSocketStore()

const installable = ref(false)
let deferred: any = null

const themeLabel = computed(() => {
  if (prefs.theme === 'light') return 'Claro'
  if (prefs.theme === 'dark') return 'Oscuro'
  return 'Sistema'
})

function setTheme(next: 'light' | 'dark' | 'system') {
  prefs.setTheme(next)
}

function setEnterToSend(v: boolean) {
  prefs.enterToSend = v
  prefs.persist()
}

function setE2ee(v: boolean) {
  prefs.e2eeEnabled = v
  prefs.persist()
}

function clearPrefs() {
  const ok = window.confirm('¿Borrar preferencias locales?')
  if (!ok) return
  localStorage.clear()
  location.reload()
}

function goBack() {
  router.push('/')
}

async function exportAll() {
  const convs = await listConversations(500)
  downloadText(
    `navibot-conversations.json`,
    JSON.stringify({ conversations: convs }, null, 2),
  )
}

async function requestNotifications() {
  const perm = await Notification.requestPermission()
  prefs.setNotificationsEnabled(perm === 'granted')
}

async function installPwa() {
  if (!deferred) return
  deferred.prompt()
  const res = await deferred.userChoice
  if (res?.outcome === 'accepted') installable.value = false
  deferred = null
}

onMounted(() => {
  window.addEventListener('beforeinstallprompt', (e: any) => {
    e.preventDefault()
    deferred = e
    installable.value = true
  })
})
</script>

<template>
  <div class="mx-auto max-w-3xl p-4 sm:p-6">
    <div class="flex items-center justify-between">
      <div class="text-lg font-semibold">Ajustes</div>
      <Button variant="secondary" size="sm" @click="goBack">Volver</Button>
    </div>

    <div class="mt-6 grid gap-4">
      <div class="rounded-xl border border-border bg-surface p-5">
        <div class="text-sm font-semibold">Preferencias</div>
        <div class="mt-4 grid gap-4">
          <TextField
            label="Nombre visible"
            :model-value="user.displayName"
            placeholder="Tu nombre"
            :maxlength="32"
            @update:model-value="user.setDisplayName"
          />

          <div class="grid gap-2">
            <div class="text-sm text-muted">Tema</div>
            <div class="flex flex-wrap gap-2">
              <Button
                :variant="prefs.theme === 'system' ? 'primary' : 'secondary'"
                size="sm"
                @click="setTheme('system')"
              >
                Sistema
              </Button>
              <Button
                :variant="prefs.theme === 'light' ? 'primary' : 'secondary'"
                size="sm"
                @click="setTheme('light')"
              >
                Claro
              </Button>
              <Button
                :variant="prefs.theme === 'dark' ? 'primary' : 'secondary'"
                size="sm"
                @click="setTheme('dark')"
              >
                Oscuro
              </Button>
              <div class="ml-auto text-xs text-muted">Actual: {{ themeLabel }}</div>
            </div>
          </div>

          <Toggle
            :model-value="prefs.enterToSend"
            label="Enter envía (Shift+Enter nueva línea)"
            @update:model-value="setEnterToSend"
          />
          <Toggle
            :model-value="prefs.e2eeEnabled"
            label="Cifrado end-to-end (experimental)"
            @update:model-value="setE2ee"
          />
        </div>
      </div>

      <div class="rounded-xl border border-border bg-surface p-5">
        <div class="text-sm font-semibold">PWA</div>
        <div class="mt-3 text-sm text-muted">
          Funciona offline con historial local. Para notificaciones push se requiere
          permiso del navegador.
        </div>
        <div class="mt-4 flex flex-col gap-2 sm:flex-row">
          <Button variant="primary" :disabled="!installable" @click="installPwa">
            Instalar
          </Button>
          <Button variant="secondary" @click="requestNotifications"
            >Permitir notificaciones</Button
          >
        </div>
        <div class="mt-2 text-xs text-muted">
          Instalación: {{ installable ? 'Disponible' : 'No disponible / ya instalada' }} ·
          Notificaciones:
          {{ prefs.notificationsEnabled ? 'Permitidas' : 'No permitidas' }}
        </div>
      </div>

      <div class="rounded-xl border border-border bg-surface p-5">
        <div class="text-sm font-semibold">Datos locales</div>
        <div class="mt-3 text-sm text-muted">
          Exporta conversaciones para backup o para compartir.
        </div>
        <div class="mt-4 flex flex-col gap-2 sm:flex-row">
          <Button variant="secondary" @click="exportAll">Exportar (JSON)</Button>
          <Button variant="danger" @click="clearPrefs">Borrar prefs</Button>
        </div>
      </div>

      <div class="rounded-xl border border-border bg-surface p-5">
        <div class="text-sm font-semibold">Diagnóstico</div>
        <div class="mt-3 grid gap-2 text-sm text-muted">
          <div>Estado: {{ ws.status }}</div>
          <div>Latencia: {{ ws.latencyMs == null ? '—' : ws.latencyMs + 'ms' }}</div>
          <div>Reconexiones: {{ ws.reconnectCount }}</div>
          <div>
            Última conexión:
            {{ ws.lastConnectedAt ? new Date(ws.lastConnectedAt).toLocaleString() : '—' }}
          </div>
        </div>
        <div class="mt-4 flex gap-2">
          <Button variant="secondary" @click="ws.connect">Probar conexión</Button>
          <Button variant="secondary" @click="ws.disconnect">Desconectar</Button>
        </div>
      </div>
    </div>
  </div>
</template>
