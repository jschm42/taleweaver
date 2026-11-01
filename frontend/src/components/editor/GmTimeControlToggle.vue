<script setup lang="ts">
// Editor toggle for AdventureTemplate.gm_time_control: whether the Game Master may change
// the in-game time (e.g. decide that a thorough search took 20 minutes).
const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()
</script>

<template>
  <div class="flex items-start justify-between gap-4 p-4 rounded-2xl bg-black/40 border border-white/10">
    <div class="space-y-1 min-w-0">
      <span class="block text-xs font-black uppercase tracking-[0.2em] text-amber-400">GM May Change Time</span>
      <p class="text-[10px] text-slate-500">
        When enabled, the Game Master can add extra time for long actions (e.g. "the search took 20 minutes")
        or jump the clock, capped by the GM limit. When disabled, time only moves by the pacing per turn and by
        scripts. Scripts can override this in-game with <code>tw.time.allow_gm_time(...)</code>.
      </p>
    </div>
    <button
      type="button"
      class="relative w-12 h-6 shrink-0 rounded-full transition-colors"
      :class="props.modelValue ? 'bg-emerald-500' : 'bg-slate-700'"
      :aria-pressed="props.modelValue"
      aria-label="GM may change time"
      @click="emit('update:modelValue', !props.modelValue)"
    >
      <div :class="['absolute top-1 w-4 h-4 bg-white rounded-full transition-all shadow-sm', props.modelValue ? 'left-7' : 'left-1']"></div>
    </button>
  </div>
</template>
