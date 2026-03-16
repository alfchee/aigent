<template>
  <div
    class="flex items-center gap-2 text-sm text-muted"
    role="status"
    aria-live="polite"
  >
    <span class="inline-flex items-center gap-1">
      <span
        class="h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
        style="animation-delay: 0ms"
      />
      <span
        class="h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
        style="animation-delay: 120ms"
      />
      <span
        class="h-1.5 w-1.5 animate-bounce rounded-full bg-muted"
        style="animation-delay: 240ms"
      />
    </span>
    <span>El agente está escribiendo…</span>
  </div>
</template>
