<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{ open: boolean; title: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const onKey = (e: KeyboardEvent) => {
  if (!props.open) return
  if (e.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <teleport to="body">
    <transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        @mousedown.self="emit('close')"
      >
        <div
          :class="cn('w-full max-w-lg rounded-xl border border-border bg-bg shadow-card')"
        >
          <div class="flex items-center justify-between border-b border-border px-5 py-4">
            <div class="text-sm font-semibold">{{ title }}</div>
            <button
              type="button"
              class="rounded-lg px-2 py-1 text-sm text-muted hover:bg-surface2/70"
              @click="emit('close')"
            >
              Cerrar
            </button>
          </div>
          <div class="p-5">
            <slot />
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 160ms ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
