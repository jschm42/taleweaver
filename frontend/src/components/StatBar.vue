<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: number
  max?: number
  color: 'crimson' | 'emerald' | 'sapphire' | 'gold'
}>()

const maxVal = computed(() => props.max ?? 200)
const pct = computed(() => Math.max(0, Math.min(100, (props.value / maxVal.value) * 100)))

const colorClasses = computed(() => {
  const map: Record<string, { bg: string, text: string }> = {
    crimson: { bg: 'bg-red-500', text: 'text-red-400' },
    emerald: { bg: 'bg-emerald-500', text: 'text-emerald-400' },
    sapphire: { bg: 'bg-blue-500', text: 'text-blue-400' },
    gold: { bg: 'bg-amber-500', text: 'text-amber-400' },
  }
  return map[props.color]
})
</script>

<template>
  <div class="flex flex-col gap-1.5 mb-3">
    <div class="flex justify-between items-center text-xs">
      <span class="font-medium text-slate-300 uppercase tracking-widest text-[10px]">{{ label }}</span>
      <span :class="['font-mono', colorClasses.text]">{{ value }}<span class="text-slate-600">/{{ maxVal }}</span></span>
    </div>
    <div class="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
      <div
        :class="['h-full rounded-full transition-all duration-500 shadow-[0_0_10px_currentColor]', colorClasses.bg, colorClasses.text]"
        :style="{ width: `${pct}%` }"
        role="progressbar"
        :aria-valuenow="value"
        :aria-valuemax="maxVal"
        :aria-label="label"
      ></div>
    </div>
  </div>
</template>
