<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchSoulPrompt, updateSoulPrompt } from '@/services/configApi'
import Button from '@/components/ui/Button.vue'
import { Check, AlertCircle } from 'lucide-vue-next'

const soul = ref('')
const loading = ref(true)
const saving = ref(false)
const error = ref<string | null>(null)
const success = ref(false)

async function load() {
  loading.value = true
  error.value = null
  try {
    soul.value = await fetchSoulPrompt()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error loading soul prompt'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = null
  success.value = false
  try {
    soul.value = await updateSoulPrompt(soul.value)
    success.value = true
    setTimeout(() => {
      success.value = false
    }, 3000)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error saving soul prompt'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div>
      <h3 class="text-sm font-semibold text-text">The "Soul" Prompt</h3>
      <p class="text-xs text-muted mt-1">
        Define la identidad base, personalidad y directrices generales que el Supervisor
        utilizará en cada conversación antes de inyectar las reglas contextuales.
      </p>
    </div>

    <div
      v-if="error"
      class="flex items-center gap-2 text-danger text-sm bg-danger/10 p-3 rounded-lg"
    >
      <AlertCircle class="w-4 h-4" />
      {{ error }}
    </div>

    <div v-if="loading" class="animate-pulse flex flex-col gap-2">
      <div class="h-32 bg-surface2 rounded-xl"></div>
    </div>

    <div v-else class="flex flex-col gap-3">
      <textarea
        v-model="soul"
        class="w-full h-48 bg-surface border border-border rounded-xl p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand/40 resize-y"
        placeholder="You are NaviBot..."
      ></textarea>

      <div class="flex items-center gap-3">
        <Button variant="primary" :disabled="saving" @click="save">
          <span v-if="saving">Guardando...</span>
          <span v-else>Guardar Identidad</span>
        </Button>

        <span
          v-if="success"
          class="flex items-center gap-1 text-brand text-sm transition-opacity"
        >
          <Check class="w-4 h-4" />
          Guardado
        </span>
      </div>
    </div>
  </div>
</template>
