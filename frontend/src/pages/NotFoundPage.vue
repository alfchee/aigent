<script setup lang="ts">
import { useRouter } from 'vue-router'
import Button from '@/components/ui/Button.vue'

const router = useRouter()
function goHome() {
  router.push('/')
}
</script>

<template>
  <div class="flex min-h-full items-center justify-center p-8">
    <div
      class="w-full max-w-md rounded-xl border border-border bg-surface p-6 text-center"
    >
      <div class="text-lg font-semibold">Página no encontrada</div>
      <div class="mt-2 text-sm text-muted">La ruta solicitada no existe.</div>
      <div class="mt-6">
        <Button variant="primary" @click="goHome">Ir al chat</Button>
      </div>
    </div>
  </div>
</template>
