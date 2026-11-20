<script setup lang="ts">
import { computed, type Component } from 'vue'
import { AlertTriangle, CheckCircle2, Info, Sparkles, XCircle } from 'lucide-vue-next'

export type NoticeTone = 'info' | 'warn' | 'danger' | 'success' | 'ai'

/** Inline note inside a page or card: a title, a sentence and an optional action. */
const props = withDefaults(defineProps<{ tone?: NoticeTone; title?: string }>(), { tone: 'info', title: '' })

const TONE: Record<NoticeTone, { icon: Component; box: string; text: string }> = {
  info: { icon: Info, box: 'border-wb-info/30 bg-wb-info-soft', text: 'text-wb-info-text' },
  warn: { icon: AlertTriangle, box: 'border-wb-warn/30 bg-wb-warn-soft', text: 'text-wb-warn-text' },
  danger: { icon: XCircle, box: 'border-wb-danger/30 bg-wb-danger-soft', text: 'text-wb-danger-text' },
  success: { icon: CheckCircle2, box: 'border-wb-accent/30 bg-wb-accent-soft', text: 'text-wb-accent-text' },
  ai: { icon: Sparkles, box: 'border-wb-ai/30 bg-wb-ai-soft', text: 'text-wb-ai-text' },
}

const style = computed(() => TONE[props.tone])
</script>

<template>
  <div
    :class="['flex flex-col gap-3 rounded-xl border p-3.5 sm:flex-row sm:items-center', style.box]"
    :role="tone === 'danger' ? 'alert' : 'status'"
  >
    <div class="flex min-w-0 flex-1 items-start gap-2.5">
      <component :is="style.icon" :class="['mt-0.5 h-4 w-4 shrink-0', style.text]" aria-hidden="true" />
      <div class="min-w-0">
        <p v-if="title" :class="['wb-subheading !text-current', style.text]">{{ title }}</p>
        <div class="wb-body text-wb-body"><slot /></div>
      </div>
    </div>
    <div v-if="$slots.action" class="shrink-0">
      <slot name="action" />
    </div>
  </div>
</template>
