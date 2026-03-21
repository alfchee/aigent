<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import RuleChip from './RuleChip.vue'

export type ActiveRule = {
  type: 'financial' | 'social' | 'coding' | 'research'
  description: string
  keywords: string[]
}

const props = withDefaults(
  defineProps<{
    userMessage?: string
    autoDetect?: boolean
  }>(),
  { userMessage: '', autoDetect: true },
)

const expanded = ref(false)

const ALL_RULES: ActiveRule[] = [
  {
    type: 'financial',
    description: 'Validar categorías de gastos y límites presupuestarios',
    keywords: [
      'gasto',
      'gastos',
      'presupuesto',
      'dinero',
      'costo',
      'costos',
      'finanzas',
      'factura',
      'facturas',
      'transacci',
      'banco',
      'tarjeta',
      'credito',
      'debito',
      'usd',
      'eur',
      'pesos',
      'income',
      'expense',
    ],
  },
  {
    type: 'social',
    description: 'Campañas IG/FB, hashtags y CTA optimizados',
    keywords: [
      'instagram',
      'facebook',
      'twitter',
      'x.com',
      'tiktok',
      'redes sociales',
      'publicar',
      'post',
      'hashtag',
      'campaña',
      'cta',
      'engagement',
      'followers',
      'likes',
      'viral',
    ],
  },
  {
    type: 'coding',
    description: 'Ejecutar código en sandbox con límites de recursos',
    keywords: [
      'codigo',
      'código',
      'python',
      'javascript',
      'script',
      'ejecutar',
      'run',
      'execute',
      'programa',
      'algoritmo',
      'function',
      'debug',
      'bug',
      'api',
      'endpoint',
      'backend',
      'frontend',
    ],
  },
  {
    type: 'research',
    description: 'Verificar fuentes con 2+ referencias autoritativas',
    keywords: [
      'busca',
      'buscar',
      'investigar',
      'investigacion',
      'research',
      'fuente',
      'fuentes',
      'referencia',
      'referencias',
      'artículo',
      'articulo',
      'estudio',
      'paper',
      'academic',
      'dato',
      'datos',
      'estadístic',
      'statistic',
    ],
  },
]

const detectedRules = computed<ActiveRule[]>(() => {
  if (!props.autoDetect || !props.userMessage) return []
  const lower = props.userMessage.toLowerCase()
  return ALL_RULES.filter((rule) => rule.keywords.some((kw) => lower.includes(kw)))
})

const hasActiveRules = computed(() => detectedRules.value.length > 0)

function toggle() {
  expanded.value = !expanded.value
}
</script>

<template>
  <div v-if="hasActiveRules || expanded" class="flex flex-col gap-2">
    <button
      type="button"
      class="flex items-center gap-2 text-xs text-muted hover:text-text transition-colors w-full"
      @click="toggle"
    >
      <span class="font-medium">
        📋 Reglas activas inyectadas ({{ detectedRules.length }})
      </span>
      <component
        :is="expanded ? ChevronUp : ChevronDown"
        class="h-3.5 w-3.5 ml-auto shrink-0"
      />
    </button>

    <div v-if="expanded" class="flex flex-wrap gap-2">
      <RuleChip
        v-for="rule in detectedRules"
        :key="rule.type"
        :rule-type="rule.type"
        :description="rule.description"
        :is-active="true"
      />
    </div>

    <div v-if="expanded && detectedRules.length > 0" class="flex flex-col gap-1.5 mt-1">
      <div
        v-for="rule in detectedRules"
        :key="rule.type"
        class="text-[11px] text-muted/80 pl-1"
      >
        <span class="font-medium capitalize">{{ rule.type }}:</span>
        {{ rule.description }}
      </div>
    </div>
  </div>
</template>
