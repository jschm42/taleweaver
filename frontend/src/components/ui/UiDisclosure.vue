<script setup lang="ts">
import { useId } from 'vue'
import { ChevronRight } from 'lucide-vue-next'

/** Show/hide block for rare options ("Advanced", "Scripts & triggers"). Closed by default. */
const open = defineModel<boolean>('open', { default: false })

withDefaults(defineProps<{ label: string; hint?: string }>(), { hint: '' })

const panelId = `disclosure-${useId()}`
</script>

<template>
  <div>
    <button
      type="button"
      class="group inline-flex items-center gap-1.5 rounded-md py-1 text-wb-muted hover:text-wb-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="open = !open"
    >
      <ChevronRight :class="['w-4 h-4 transition-transform', open ? 'rotate-90' : '']" aria-hidden="true" />
      <span class="wb-label !text-current">{{ label }}</span>
      <span v-if="hint && !open" class="wb-hint">· {{ hint }}</span>
    </button>
    <div v-show="open" :id="panelId" class="mt-3">
      <slot />
    </div>
  </div>
</template>
