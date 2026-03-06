<script setup lang="ts">
import { computed } from 'vue'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'
import jsonLang from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import yaml from 'highlight.js/lib/languages/yaml'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('css', css)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('json', jsonLang)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('yaml', yaml)

const props = defineProps<{
  code: string
  language?: string
}>()

const highlighted = computed(() => {
  const lang = (props.language || 'plaintext').toLowerCase()
  try {
    if (hljs.getLanguage(lang)) {
      return hljs.highlight(props.code, { language: lang }).value
    }
  } catch {
    return hljs.highlightAuto(props.code).value
  }
  return hljs.highlightAuto(props.code).value
})
</script>

<template>
  <pre
    class="text-sm overflow-auto border border-slate-200 rounded bg-white p-3"
  ><code class="hljs" v-html="highlighted" /></pre>
</template>

<style>
@import url('highlight.js/styles/github.css');
</style>
