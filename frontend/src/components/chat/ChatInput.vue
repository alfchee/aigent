<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Button from '@/components/ui/Button.vue'
import IconButton from '@/components/ui/IconButton.vue'
import { Send, CornerDownLeft, Wand2 } from 'lucide-vue-next'
import { usePreferencesStore } from '@/stores/preferences'
import { cn } from '@/lib/utils'

const emit = defineEmits<{ (e: 'send', text: string): void }>()
const prefs = usePreferencesStore()

const text = ref('')
const ta = ref<HTMLTextAreaElement | null>(null)
const maxLen = computed(() => prefs.maxMessageLength)
const remaining = computed(() => Math.max(0, maxLen.value - text.value.length))

const showCommands = computed(
  () => text.value.trimStart().startsWith('/') || text.value.trimStart().startsWith('@'),
)
const suggestions = computed(() => {
  const t = text.value.trimStart()
  if (t.startsWith('/')) {
    return [
      { key: '/new', label: 'Nueva conversación' },
      { key: '/export', label: 'Exportar conversación' },
      { key: '/clear', label: 'Limpiar borrador' },
    ]
  }
  if (t.startsWith('@')) {
    return [
      { key: '@default', label: 'Agente por defecto' },
      { key: '@planner', label: 'Agente planificador' },
    ]
  }
  return []
})

function autosize() {
  if (!ta.value) return
  ta.value.style.height = 'auto'
  ta.value.style.height = `${Math.min(220, ta.value.scrollHeight)}px`
}

watch(text, () => nextTick(autosize))

function onKeydown(e: KeyboardEvent) {
  if (!prefs.enterToSend) return
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  const trimmed = text.value.trim()
  if (!trimmed) return
  if (trimmed.length > maxLen.value) return
  emit('send', trimmed)
  text.value = ''
  nextTick(autosize)
}

function applySuggestion(key: string) {
  if (key === '/clear') {
    text.value = ''
    return
  }
  text.value = key + ' '
}
</script>

<template>
  <div class="rounded-xl border border-border bg-surface p-3">
    <div class="flex items-end gap-2">
      <div class="relative flex-1">
        <textarea
          ref="ta"
          v-model="text"
          rows="1"
          class="w-full resize-none rounded-xl border border-border bg-bg px-3 py-2 text-sm leading-6 outline-none transition focus-visible:ring-2 focus-visible:ring-brand/40"
          :maxlength="maxLen"
          placeholder="Escribe un mensaje… (Enter envía, Shift+Enter nueva línea)"
          aria-label="Escribir mensaje"
          @keydown="onKeydown"
          @input="autosize"
        />

        <div
          v-if="showCommands && suggestions.length"
          class="absolute bottom-full mb-2 w-full overflow-hidden rounded-xl border border-border bg-bg shadow-card"
          role="listbox"
          aria-label="Sugerencias"
        >
          <button
            v-for="s in suggestions"
            :key="s.key"
            type="button"
            class="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-surface2/60"
            @click="applySuggestion(s.key)"
          >
            <span class="font-medium">{{ s.key }}</span>
            <span class="text-xs text-muted">{{ s.label }}</span>
          </button>
        </div>
      </div>

      <IconButton
        aria-label="Atajos"
        size="md"
        variant="ghost"
        @click="applySuggestion('/new')"
      >
        <Wand2 class="h-4 w-4" />
      </IconButton>

      <Button
        variant="primary"
        :disabled="!text.trim() || text.trim().length > maxLen"
        @click="send"
      >
        <Send class="h-4 w-4" />
        <span class="hidden sm:inline">Enviar</span>
        <span class="hidden sm:inline text-white/70">·</span>
        <span class="hidden sm:inline-flex items-center gap-1 text-white/80">
          <CornerDownLeft class="h-4 w-4" />
          Enter
        </span>
      </Button>
    </div>

    <div class="mt-2 flex items-center justify-between text-xs text-muted">
      <span :class="cn(remaining < 120 ? 'text-danger' : '')"
        >{{ remaining }} caracteres</span
      >
      <span v-if="!prefs.enterToSend"
        >Enter inserta línea; usa el botón para enviar.</span
      >
    </div>
  </div>
</template>
