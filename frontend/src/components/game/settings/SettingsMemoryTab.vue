<script setup lang="ts">
import { computed } from 'vue'
import { BrainCircuit, Sparkles } from 'lucide-vue-next'
import SettingCard from './SettingCard.vue'
import SettingToggle from './SettingToggle.vue'
import NarrationStylePicker from './NarrationStylePicker.vue'
import type { NarrationStyle } from './narrationStyles'

const narrationStyle = defineModel<NarrationStyle>('narrationStyle', { required: true })
const turns = defineModel<number>('turns', { required: true })
const enableCompression = defineModel<boolean>('enableCompression', { required: true })

const MIN_TURNS = 1
const MAX_TURNS = 100

const tokenProfile = computed(() => {
  if (turns.value <= 10) {
    return {
      label: 'Balanced',
      class: 'text-amber-300 border-amber-500/30 bg-amber-500/10',
      description: 'Rich continuity across scenes with efficient token usage. Recommended for most adventures.',
    }
  }
  if (turns.value <= 30) {
    return {
      label: 'Extended Memory',
      class: 'text-cyan-300 border-cyan-500/30 bg-cyan-500/10',
      description: 'Keeps more recent turns verbatim. Moderately higher token consumption per turn.',
    }
  }
  return {
    label: 'Deep Memory',
    class: 'text-purple-300 border-purple-500/30 bg-purple-500/10',
    description: 'Extensive recall for intricate plots, but every turn consumes significantly more LLM tokens.',
  }
})

function handleInput(event: Event) {
  const raw = Number((event.target as HTMLInputElement).value)
  if (isNaN(raw)) {
    return
  }
  turns.value = Math.min(MAX_TURNS, Math.max(MIN_TURNS, raw))
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="text-xs leading-relaxed text-slate-400">
      Shape how the narrator writes and how much of your story it remembers.
    </p>

    <NarrationStylePicker v-model="narrationStyle" />

    <SettingCard
      title="Narrator Turn Memory"
      description="Number of recent turns passed verbatim to the narrator with every action."
      hint="A turn is one narrator response together with what started it: usually your action, but entering a new scene or starting a new sequence also opens a turn of its own. Older turns fall out of the window or are compressed (see below)."
    >
      <template #control>
        <div class="flex shrink-0 items-center gap-1.5 rounded-xl border border-white/15 bg-black/50 px-2.5 py-1.5">
          <input
            type="number"
            :min="MIN_TURNS"
            :max="MAX_TURNS"
            :value="turns"
            aria-label="Turn memory"
            class="w-10 bg-transparent text-center font-mono text-sm font-bold text-white focus:outline-none"
            @input="handleInput"
          />
          <span class="text-[10px] font-bold uppercase tracking-wider text-amber-400">Turns</span>
        </div>
      </template>

      <div class="mt-4 space-y-2">
        <input
          type="range"
          :min="MIN_TURNS"
          :max="MAX_TURNS"
          :value="turns"
          aria-label="Turn memory slider"
          class="h-2 w-full cursor-pointer rounded-lg bg-slate-800 accent-amber-500"
          @input="handleInput"
        />
        <div class="flex items-center justify-between text-[10px] uppercase tracking-widest text-slate-500">
          <span>1</span>
          <span class="font-bold text-amber-400">10 · Default</span>
          <span>100</span>
        </div>
      </div>

      <div :class="['mt-3 rounded-xl border p-3 transition-colors', tokenProfile.class]">
        <div class="flex items-center gap-2">
          <BrainCircuit class="h-4 w-4 shrink-0" />
          <span class="text-[11px] font-black uppercase tracking-wider">{{ tokenProfile.label }}</span>
        </div>
        <p class="mt-1 text-xs leading-relaxed opacity-90">{{ tokenProfile.description }}</p>
      </div>
    </SettingCard>

    <SettingCard
      title="History Compression"
      badge="English"
      description="Turns that leave the memory window are condensed into a chronicle summary that the narrator keeps reading."
      hint="The summary is always written in English to keep it compact for the model, independent of your Bable Fish language. Turn this off only if the narrator should forget everything outside the memory window."
    >
      <template #control>
        <SettingToggle v-model="enableCompression" label="Automatic history compression" />
      </template>
    </SettingCard>

    <div class="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3.5 text-xs leading-relaxed text-slate-400">
      <Sparkles class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
      <span>
        Memory changes apply to your next action. Intermediate game events such as dice rolls are formatted
        automatically and do not count as turns.
      </span>
    </div>
  </div>
</template>
