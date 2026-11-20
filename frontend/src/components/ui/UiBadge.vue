<script setup lang="ts">
export type BadgeTone = 'neutral' | 'accent' | 'ai' | 'info' | 'warn' | 'danger'

withDefaults(defineProps<{ tone?: BadgeTone }>(), { tone: 'neutral' })

const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: 'bg-wb-raised text-wb-muted border-wb-line',
  accent: 'bg-wb-accent-soft text-wb-accent-text border-wb-accent/30',
  ai: 'bg-wb-ai-soft text-wb-ai-text border-wb-ai/30',
  info: 'bg-wb-info-soft text-wb-info-text border-wb-info/30',
  warn: 'bg-wb-warn-soft text-wb-warn-text border-wb-warn/30',
  danger: 'bg-wb-danger-soft text-wb-danger-text border-wb-danger/30',
}
</script>

<template>
  <span :class="['inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 wb-hint font-medium tabular-nums', TONE_CLASS[tone]]">
    <slot />
  </span>
</template>
