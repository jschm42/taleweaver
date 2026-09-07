<script setup lang="ts">
import { computed } from 'vue'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

type RuleMode = 'rpg' | 'story' | 'chat'

const props = defineProps<{
  modelValue: RuleMode
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: RuleMode): void
}>()

const ruleModeHelp = computed(() => {
  if (props.modelValue === 'rpg') {
    return 'The Game Master enforces strict rules, inventory checks, and combat mechanics.'
  }
  if (props.modelValue === 'story') {
    return 'Story and atmosphere in the foreground. Balanced mechanics with narrative priority.'
  }
  return 'Story, atmosphere, and conversational roleplay. No strict combat or rule barriers.'
})
</script>

<template>
  <div class="space-y-3 md:space-y-4">
    <div class="flex items-center justify-between gap-2">
      <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Rule Enforcement Mode</label>
      <InfoPopoverButton title="Rule Enforcement" :text="CREATE_ADVENTURE_HELP_TEXTS.ruleEnforcement" />
    </div>

    <div class="grid grid-cols-3 gap-2 sm:gap-3">
      <button
        v-for="mode in (['rpg', 'story', 'chat'] as RuleMode[])"
        :key="mode"
        type="button"
        @click="emit('update:modelValue', mode)"
        class="px-2 sm:px-3 md:px-4 py-3 sm:py-3.5 md:py-4 rounded-2xl border-2 transition-all flex flex-col items-center gap-1 cursor-pointer select-none active:scale-95"
        :class="props.modelValue === mode ? 'border-aether-primary bg-aether-primary/10 text-white shadow-md' : 'border-white/5 bg-white/5 text-white/40 hover:border-white/10 hover:text-white/70'"
      >
        <span class="text-xxs sm:text-xs font-black uppercase tracking-widest">{{ mode === 'rpg' ? 'RPG' : mode }}</span>
      </button>
    </div>

    <p class="text-xxs text-white/40 uppercase tracking-widest text-center px-2">
      {{ ruleModeHelp }}
    </p>
  </div>
</template>
