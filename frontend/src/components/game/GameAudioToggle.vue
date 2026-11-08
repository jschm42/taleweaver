<script setup lang="ts">
import { computed } from 'vue'
import { AudioLines, VolumeX, Loader2, Square } from 'lucide-vue-next'

const props = defineProps<{
  muted: boolean
  volume: number
  generating: boolean
  error?: string
  /** A track is playing right now (the stop button is shown). */
  playing?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
  (e: 'stop'): void
  (e: 'volume', value: number): void
}>()

const title = computed((): string => {
  if (props.error) return `Audio: ${props.error}`
  if (props.generating) return 'Composing new audio…'
  return props.muted ? 'Play background audio' : 'Mute background audio'
})

function onVolume(event: Event): void {
  emit('volume', Number((event.target as HTMLInputElement).value))
}
</script>

<template>
  <div class="group flex items-center gap-2 rounded-full border border-white/10 bg-black/50 px-2 py-1.5 backdrop-blur">
    <button
      type="button"
      class="p-1 text-slate-300 hover:text-aether-primary transition-colors"
      :class="{ 'text-rose-400': !!error }"
      :title="title"
      :aria-label="title"
      :aria-pressed="!muted"
      @click.stop="emit('toggle')"
    >
      <Loader2 v-if="generating && !muted" class="w-4 h-4 animate-spin" />
      <VolumeX v-else-if="muted" class="w-4 h-4" />
      <AudioLines v-else class="w-4 h-4" />
    </button>
    <button
      v-if="!muted"
      type="button"
      class="p-1 text-slate-300 hover:text-rose-300 transition-colors"
      title="Stop background audio"
      aria-label="Stop background audio"
      @click.stop="emit('stop')"
    >
      <Square class="w-3.5 h-3.5 fill-current" />
    </button>
    <input
      v-if="!muted"
      type="range"
      min="0"
      max="1"
      step="0.05"
      :value="volume"
      aria-label="Audio volume"
      class="hidden w-20 accent-aether-primary group-hover:block group-focus-within:block"
      @input="onVolume"
    />
  </div>
</template>
