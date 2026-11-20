<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy } from 'lucide-vue-next'

/** An entity id in mono type; click copies it to the clipboard. */
const props = defineProps<{ value: string }>()

const copied = ref(false)

async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    copied.value = false
  }
}
</script>

<template>
  <button
    type="button"
    class="inline-flex items-center gap-1 rounded-md border border-wb-line bg-wb-raised px-1.5 py-0.5 wb-mono text-wb-muted hover:text-wb-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
    :title="copied ? 'Copied' : 'Copy the id'"
    :aria-label="`Copy id ${value}`"
    @click="copy"
  >
    {{ value }}
    <component :is="copied ? Check : Copy" class="h-3 w-3" aria-hidden="true" />
  </button>
</template>
