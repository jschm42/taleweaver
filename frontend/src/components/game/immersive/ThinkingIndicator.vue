<script setup lang="ts">
/**
 * ThinkingIndicator — Compact "GM is working" badge: a pulsing brain with the turn pass
 * (1 = rules / Pass 1, 2 = narration / Pass 2). The full status text stays in the tooltip.
 */
import { computed } from 'vue'
import { Brain } from 'lucide-vue-next'

const props = defineProps<{
  statusText?: string
}>()

// Status lines the backend sends once the narration pass has started.
const NARRATION_STATUS = /narrat|chronicle|reflects on the battle/i

const pass = computed(() => (NARRATION_STATUS.test(props.statusText || '') ? 2 : 1))
const label = computed(() => props.statusText || (pass.value === 2 ? 'Narrating...' : 'Validating rules...'))
</script>

<template>
  <div
    class="flex items-center gap-1 px-2 py-1 rounded-full bg-amber-950/80 border border-amber-400/70 shadow-[0_0_20px_rgba(251,191,36,0.3)] backdrop-blur-xl animate-fade-in shrink-0 select-none"
    :title="label"
    role="status"
    :aria-label="label"
  >
    <div class="relative flex items-center justify-center w-5 h-5">
      <div class="absolute inset-0 rounded-full bg-amber-400/20 animate-ping"></div>
      <Brain class="w-4 h-4 text-amber-400 animate-pulse" />
    </div>
    <span class="text-xs font-black tabular-nums text-amber-300 pr-0.5">{{ pass }}</span>
  </div>
</template>
