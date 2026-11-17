<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { Info } from 'lucide-vue-next'

/** A small "i" button that shows help text in a popover. Closes on outside click and Esc. */
withDefaults(defineProps<{ title?: string; text?: string }>(), { title: 'Help', text: '' })

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const panelId = `info-${useId()}`

function handleDocumentClick(event: MouseEvent): void {
  const target = event.target as Node | null
  if (open.value && rootEl.value && target && !rootEl.value.contains(target)) {
    open.value = false
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (open.value && event.key === 'Escape') {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <span ref="rootEl" class="relative inline-flex shrink-0">
    <button
      type="button"
      class="inline-flex h-5 w-5 items-center justify-center rounded-full text-wb-muted hover:text-wb-info-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
      :aria-label="`Show help for ${title}`"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="open = !open"
    >
      <Info class="w-4 h-4" aria-hidden="true" />
    </button>
    <div
      v-if="open"
      :id="panelId"
      role="dialog"
      :aria-label="title"
      class="absolute left-0 top-7 z-50 w-[calc(100vw-2rem)] sm:w-72 max-w-sm rounded-xl border border-wb-line-strong bg-wb-overlay shadow-wb-float p-3 font-wb"
    >
      <p class="wb-subheading mb-1">{{ title }}</p>
      <div class="wb-hint !text-wb-body break-words whitespace-pre-wrap">
        <slot>{{ text }}</slot>
      </div>
    </div>
  </span>
</template>
