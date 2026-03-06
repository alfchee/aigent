<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  html: string
}>()

const safeHtml = computed(() => {
  const input = props.html || ''
  return input.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
})
</script>

<template>
  <iframe
    class="w-full h-full bg-white"
    :srcdoc="safeHtml"
    sandbox=""
    referrerpolicy="no-referrer"
  />
</template>
