<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { Wifi, WifiOff, Loader2 } from 'lucide-vue-next'
import { WebSocketService } from '../../services/websocket'

const wsService = WebSocketService.getInstance()

const reconnectAttempt = ref(0)
const maxReconnectAttempts = ref(10)
const isReconnecting = ref(false)

// Connection status: 'connected' | 'disconnected' | 'reconnecting'
const connectionStatus = computed(() => {
  if (wsService.isConnected.value) return 'connected'
  if (isReconnecting.value) return 'reconnecting'
  return 'disconnected'
})

const statusText = computed(() => {
  switch (connectionStatus.value) {
    case 'connected':
      return 'Conectado'
    case 'reconnecting':
      return `Reconectando (${reconnectAttempt.value}/${maxReconnectAttempts.value})...`
    default:
      return 'Desconectado'
  }
})

// Listen for reconnection events
onMounted(() => {
  wsService.on('connection.reconnecting', (data: { attempt: number; maxAttempts: number }) => {
    isReconnecting.value = true
    reconnectAttempt.value = data.attempt
    maxReconnectAttempts.value = data.maxAttempts
  })

  wsService.on('connection.open', () => {
    isReconnecting.value = false
    reconnectAttempt.value = 0
  })

  wsService.on('connection.max_reconnect_attempts', () => {
    isReconnecting.value = false
  })
})

// Expose for parent to check connection status
defineExpose({
  connectionStatus,
  isConnected: computed(() => wsService.isConnected.value),
})
</script>

<template>
  <div class="flex items-center gap-2">
    <!-- Connection Status Indicator -->
    <div
      class="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-colors"
      :class="[
        connectionStatus === 'connected'
          ? 'bg-green-50 text-green-700'
          : connectionStatus === 'reconnecting'
            ? 'bg-yellow-50 text-yellow-700'
            : 'bg-red-50 text-red-700',
      ]"
      :title="statusText"
    >
      <!-- Connected -->
      <Wifi v-if="connectionStatus === 'connected'" class="w-3.5 h-3.5" />

      <!-- Reconnecting -->
      <Loader2 v-else-if="connectionStatus === 'reconnecting'" class="w-3.5 h-3.5 animate-spin" />

      <!-- Disconnected -->
      <WifiOff v-else class="w-3.5 h-3.5" />

      <span class="hidden sm:inline">{{ statusText }}</span>
    </div>
  </div>
</template>
