<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useDebounceFn } from '@vueuse/core'

const props = defineProps<{
  modelValue: string
  options: string[]
  placeholder?: string
  loading?: boolean
  error?: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'search', query: string): void
}>()

const isOpen = ref(false)
const searchQuery = ref('')
const highlightedIndex = ref(-1)
const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLUListElement | null>(null)

// Initialize search query with modelValue
watch(
  () => props.modelValue,
  (newVal) => {
    // Only update query if it's different and we are NOT currently typing/searching
    // actually, we should always sync it if the parent updates it.
    // But if user is typing, we don't want to overwrite?
    // If user types "gem", modelValue might still be old value until selection.
    // So we only sync if the component is NOT open/active?
    if (!isOpen.value) {
      searchQuery.value = newVal
    }
  },
  { immediate: true },
)

const filteredOptions = computed(() => {
  const query = searchQuery.value.toLowerCase().trim()
  if (!query) return props.options

  return props.options.filter((option) => option.toLowerCase().includes(query))
})

const debouncedSearch = useDebounceFn((query: string) => {
  emit('search', query)
}, 300)

const onInput = (e: Event) => {
  const target = e.target as HTMLInputElement
  searchQuery.value = target.value
  isOpen.value = true
  highlightedIndex.value = 0
  debouncedSearch(target.value)
}

const onFocus = () => {
  isOpen.value = true
}

const onBlur = () => {
  // We use mousedown.prevent on options to prevent blur when clicking them.
  // So this onBlur only fires when clicking outside or tabbing away.
  isOpen.value = false

  // Reset query to modelValue if valid, or clear if invalid?
  // If user typed something that isn't selected, revert to modelValue.
  if (props.modelValue) {
    searchQuery.value = props.modelValue
  } else {
    searchQuery.value = ''
  }
}

const selectOption = (option: string) => {
  emit('update:modelValue', option)
  searchQuery.value = option
  isOpen.value = false
  // Keep focus on input? Yes, standard behavior.
}

const clearSelection = () => {
  emit('update:modelValue', '')
  searchQuery.value = ''
  inputRef.value?.focus()
  isOpen.value = true
}

const onKeydown = (e: KeyboardEvent) => {
  if (props.disabled) return

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      if (!isOpen.value) isOpen.value = true
      if (highlightedIndex.value < filteredOptions.value.length - 1) {
        highlightedIndex.value++
        scrollToHighlighted()
      }
      break
    case 'ArrowUp':
      e.preventDefault()
      if (!isOpen.value) isOpen.value = true
      if (highlightedIndex.value > 0) {
        highlightedIndex.value--
        scrollToHighlighted()
      }
      break
    case 'Enter':
      e.preventDefault()
      if (
        isOpen.value &&
        highlightedIndex.value >= 0 &&
        filteredOptions.value[highlightedIndex.value]
      ) {
        selectOption(filteredOptions.value[highlightedIndex.value])
      }
      break
    case 'Escape':
      e.preventDefault()
      isOpen.value = false
      inputRef.value?.blur()
      break
    case 'Tab':
      isOpen.value = false
      break
  }
}

const scrollToHighlighted = () => {
  nextTick(() => {
    if (!listRef.value) return
    // children might include the "No models" li, need to be careful
    // but filteredOptions.length check handles empty list case for navigation
    // Wait, if list is empty, highlightedIndex should be -1.

    const items = listRef.value.querySelectorAll('[role="option"]')
    if (items[highlightedIndex.value]) {
      items[highlightedIndex.value].scrollIntoView({ block: 'nearest' })
    }
  })
}

// Helper to escape HTML characters
const escapeHtml = (text: string) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// Highlight matching text
const highlightMatch = (text: string) => {
  if (!searchQuery.value) return escapeHtml(text)
  if (text === searchQuery.value) return escapeHtml(text)

  const query = searchQuery.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

  // This is a bit tricky because we escaped the text, but we want to highlight original characters.
  // Simple approach: split by query (case insensitive) and wrap.
  // But strictly we should match against original text, then escape parts.

  const parts = text.split(new RegExp(`(${query})`, 'gi'))
  return parts
    .map((part) => {
      if (part.toLowerCase() === searchQuery.value.toLowerCase()) {
        return `<span class="bg-sky-100 text-sky-700 font-medium">${escapeHtml(part)}</span>`
      }
      return escapeHtml(part)
    })
    .join('')
}
</script>

<template>
  <div class="relative w-full group">
    <div class="relative">
      <input
        ref="inputRef"
        type="text"
        role="combobox"
        aria-autocomplete="list"
        :aria-expanded="isOpen"
        aria-haspopup="listbox"
        :value="searchQuery"
        :placeholder="placeholder"
        :disabled="disabled"
        class="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all placeholder:text-slate-400"
        :class="{ 'pr-10': loading || (modelValue && !disabled) }"
        @input="onInput"
        @focus="onFocus"
        @blur="onBlur"
        @keydown="onKeydown"
      />

      <!-- Loading Indicator -->
      <div v-if="loading" class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
        <svg
          class="animate-spin h-4 w-4 text-sky-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>
      </div>

      <!-- Clear Button -->
      <button
        v-else-if="modelValue && !disabled"
        type="button"
        tabindex="-1"
        aria-label="Clear selection"
        class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-red-500 transition-colors p-1 rounded-full hover:bg-slate-100"
        @click.stop="clearSelection"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          ></path>
        </svg>
      </button>

      <!-- Chevron (if empty) -->
      <div
        v-else
        class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          ></path>
        </svg>
      </div>
    </div>

    <!-- Error Message -->
    <p v-if="error" class="mt-1 text-xs text-red-500 flex items-center gap-1">
      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        ></path>
      </svg>
      {{ error }}
    </p>

    <!-- Dropdown List -->
    <div
      v-show="isOpen"
      class="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-xl max-h-60 overflow-y-auto overflow-x-hidden animate-in fade-in zoom-in-95 duration-100"
      @mousedown.prevent
    >
      <ul ref="listRef" role="listbox">
        <li
          v-if="filteredOptions.length === 0"
          class="px-4 py-3 text-sm text-slate-500 text-center italic"
        >
          No matching models found
        </li>

        <li
          v-for="(option, index) in filteredOptions"
          :key="option"
          role="option"
          :aria-selected="option === modelValue"
          class="px-4 py-2.5 text-sm cursor-pointer transition-colors border-l-2"
          :class="{
            'bg-sky-50 border-sky-500 text-sky-900': index === highlightedIndex,
            'border-transparent text-slate-700 hover:bg-slate-50': index !== highlightedIndex,
            'font-semibold bg-slate-50': option === modelValue,
          }"
          @mousedown.prevent="selectOption(option)"
          @mouseenter="highlightedIndex = index"
        >
          <!-- eslint-disable-next-line vue/no-v-html -->
          <span class="block truncate" v-html="highlightMatch(option)"></span>
        </li>
      </ul>
    </div>
  </div>
</template>
