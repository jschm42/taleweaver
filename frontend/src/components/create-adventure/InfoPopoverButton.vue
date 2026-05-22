<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{
  title?: string
  text: string
}>(), {
  title: 'Help',
})

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)

const handleDocumentClick = (event: MouseEvent) => {
  if (!open.value) return
  const target = event.target as Node | null
  if (rootEl.value && target && !rootEl.value.contains(target)) {
    open.value = false
  }
}

const toggle = () => {
  open.value = !open.value
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <div ref="rootEl" class="relative inline-flex">
    <button
      type="button"
      class="w-6 h-6 rounded-full border border-white/20 text-white/80 hover:text-white hover:border-white/40 bg-black/30 transition-all text-[11px] font-black"
      :aria-label="`Show help for ${title}`"
      @click="toggle"
    >
      ?
    </button>

    <div
      v-if="open"
      class="absolute right-0 top-8 z-30 w-64 rounded-xl border border-cyan-400/30 bg-slate-950/95 backdrop-blur-lg shadow-2xl p-3"
    >
      <p class="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-300 mb-2">{{ title }}</p>
      <p class="text-xs leading-relaxed text-slate-200">{{ text }}</p>
    </div>
  </div>
</template>
