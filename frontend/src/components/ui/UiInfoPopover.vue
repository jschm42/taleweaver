<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { CircleHelp, Info } from 'lucide-vue-next'

/**
 * A small "i" (or "?") button that shows help text in a popover. Closes on outside click and Esc.
 * `align="end"` opens the panel towards the left, for buttons at the right edge of a card.
 */
withDefaults(
  defineProps<{ title?: string; text?: string; icon?: 'info' | 'help'; align?: 'start' | 'end'; wide?: boolean }>(),
  { title: 'Help', text: '', icon: 'info', align: 'start', wide: false },
)

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
      <CircleHelp v-if="icon === 'help'" class="w-4 h-4" aria-hidden="true" />
      <Info v-else class="w-4 h-4" aria-hidden="true" />
    </button>
    <div
      v-if="open"
      :id="panelId"
      role="dialog"
      :aria-label="title"
      class="absolute top-7 z-50 w-[calc(100vw-2rem)] max-w-sm rounded-xl border border-wb-line-strong bg-wb-overlay shadow-wb-float p-3 font-wb"
      :class="[align === 'end' ? 'right-0' : 'left-0', wide ? 'sm:w-96' : 'sm:w-72']"
    >
      <p class="wb-subheading mb-1">{{ title }}</p>
      <div class="wb-hint !text-wb-body break-words whitespace-pre-wrap">
        <slot>{{ text }}</slot>
      </div>
    </div>
  </span>
</template>
