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
import { AGENT_OPTIONS } from '@/config/agents'
import {
  fetchTechnicalPanelData,
  type TechnicalPanelData,
} from '@/services/operationsApi'

const router = useRouter()
const prefs = usePreferencesStore()
const user = useUserConfigStore()
const ws = useWebSocketStore()

const installable = ref(false)
const technical = ref<TechnicalPanelData | null>(null)
const technicalLoading = ref(false)
const technicalError = ref<string | null>(null)
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

async function loadTechnicalPanel() {
  technicalLoading.value = true
  technicalError.value = null
  try {
    technical.value = await fetchTechnicalPanelData()
  } catch (err) {
    technicalError.value =
      err instanceof Error ? err.message : 'No se pudo cargar panel técnico'
  } finally {
    technicalLoading.value = false
  }
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

          <div class="grid gap-2">
            <div class="text-sm text-muted">Agente predeterminado</div>
            <div class="flex flex-wrap gap-2">
              <Button
                v-for="agent in AGENT_OPTIONS"
                :key="agent.id"
                :variant="user.activeAgentId === agent.id ? 'primary' : 'secondary'"
                size="sm"
                @click="user.setActiveAgentId(agent.id)"
              >
                @{{ agent.id }}
              </Button>
            </div>
          </div>
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

      <div class="rounded-xl border border-border bg-surface p-5">
        <div class="text-sm font-semibold">Panel técnico backend</div>
        <div class="mt-3 text-sm text-muted">
          Consulta métricas de sandbox y snapshot activo de roles.
        </div>
        <div class="mt-4 flex gap-2">
          <Button
            variant="secondary"
            :disabled="technicalLoading"
            @click="loadTechnicalPanel"
          >
            {{ technicalLoading ? 'Cargando…' : 'Refrescar panel' }}
          </Button>
        </div>
        <div v-if="technicalError" class="mt-3 text-xs text-danger">
          {{ technicalError }}
        </div>
        <div v-if="technical" class="mt-4 grid gap-3 text-sm">
          <div class="rounded-lg border border-border bg-bg p-3">
            <div class="font-medium">Roles</div>
            <div class="mt-2 grid gap-1 text-xs text-muted">
              <div>Supervisor: {{ technical.roles.supervisorName }}</div>
              <div>Workers: {{ technical.roles.workerCount }}</div>
              <div>
                Actualizado: {{ new Date(technical.roles.updatedAt).toLocaleString() }}
              </div>
              <div class="truncate">Config: {{ technical.roles.configPath }}</div>
            </div>
            <div class="mt-2 flex flex-wrap gap-1">
              <span
                v-for="worker in technical.roles.workers"
                :key="worker.id"
                class="inline-flex items-center rounded-full border border-border px-2 py-0.5 text-[11px] text-muted"
              >
                {{ worker.id }} · {{ worker.skills.length }} skills
              </span>
            </div>
          </div>
          <div class="rounded-lg border border-border bg-bg p-3">
            <div class="font-medium">Sandbox metrics</div>
            <div class="mt-2 grid gap-2">
              <div
                v-for="[scope, bucket] in Object.entries(technical.metrics)"
                :key="scope"
                class="rounded-md border border-border px-2 py-2 text-xs text-muted"
              >
                <div class="font-medium text-text">{{ scope }}</div>
                <div class="mt-1">
                  runs={{ bucket.total_runs }} · ok={{ bucket.success_runs }} · policy={{
                    bucket.policy_violations
                  }}
                </div>
                <div>
                  timeout={{ bucket.timeouts }} · errors={{ bucket.execution_errors }} ·
                  avg={{ bucket.avg_duration_ms }}ms
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
