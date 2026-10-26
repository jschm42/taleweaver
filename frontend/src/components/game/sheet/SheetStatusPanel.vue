<script setup lang="ts">
/**
 * SheetStatusPanel — Active ailments and buffs of the hero.
 */
const props = defineProps<{
  effects: string[]
}>()

const POSITIVE_KEYWORDS = ['bless', 'boost', 'strength', 'regen', 'shield', 'grace', 'haste', 'focus', 'sharp', 'vitality', 'aura', 'vigor', 'protect', 'might']

// First matching keyword group wins.
const STATUS_ICONS: [string[], string][] = [
  [['poison', 'venom'], 'ra-poison-cloud'],
  [['bleed', 'wound'], 'ra-bleeding-hearts'],
  [['burn', 'fire'], 'ra-burning-embers'],
  [['freeze', 'frost', 'chill'], 'ra-frost-fire'],
  [['curse'], 'ra-skull'],
  [['blind', 'dark'], 'ra-eyeball'],
  [['stun', 'daze', 'paralyz'], 'ra-lightning-trio'],
  [['fatigue', 'exhaust', 'tired'], 'ra-droplet'],
  [['bless', 'holy'], 'ra-sun'],
  [['shield', 'armor', 'protect'], 'ra-shield'],
  [['haste', 'speed', 'quick'], 'ra-fast-forward'],
  [['strength', 'might', 'rage'], 'ra-muscle-up'],
]

const isPositive = (effect: string): boolean => {
  const name = effect.toLowerCase()
  return POSITIVE_KEYWORDS.some((kw) => name.includes(kw))
}

const statusIcon = (effect: string): string => {
  const name = effect.toLowerCase()
  const match = STATUS_ICONS.find(([keywords]) => keywords.some((kw) => name.includes(kw)))
  if (match) return match[1]
  return isPositive(effect) ? 'ra-aura' : 'ra-heart-burn'
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- No effects: peak condition -->
    <div
      v-if="props.effects.length === 0"
      class="tw-dialog-slot !border-solid flex-grow flex flex-col items-center justify-center p-8 text-center my-auto"
    >
      <div class="w-16 h-16 sm:w-20 sm:h-20 rounded-3xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-4 shadow-[0_0_30px_rgba(16,185,129,0.15)]">
        <i class="ra ra-shield text-3xl sm:text-4xl text-emerald-400"></i>
      </div>
      <h4 class="tw-dialog-title text-lg sm:text-xl mb-2">Peak Condition</h4>
      <p class="tw-muted text-xs sm:text-sm max-w-md leading-relaxed">
        Your character is free of any ailments, injuries, curses, or lingering debuffs. All vital systems are functioning normally.
      </p>
      <div class="mt-4 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-500 text-xxs font-bold uppercase tracking-wider flex items-center gap-1.5">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
        Active Condition: Optimal
      </div>
    </div>

    <!-- Active effects -->
    <div v-else class="space-y-3">
      <div class="flex items-center justify-between mb-2">
        <h4 class="tw-panel-title tw-muted">Active Effects</h4>
        <span class="tw-dialog-eyebrow text-xxs font-mono">{{ props.effects.length }} active</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div
          v-for="effect in props.effects"
          :key="effect"
          class="tw-card p-4 border-l-4 flex items-start gap-3.5 shadow-lg"
          :class="isPositive(effect) ? '!border-l-emerald-500' : '!border-l-rose-500'"
        >
          <div
            class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border"
            :class="isPositive(effect) ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-500' : 'bg-rose-500/15 border-rose-500/30 text-rose-500'"
          >
            <i :class="['ra text-xl', statusIcon(effect)]"></i>
          </div>

          <div class="min-w-0 flex-grow">
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-bold capitalize truncate">{{ effect }}</span>
              <span
                class="text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded border shrink-0"
                :class="isPositive(effect) ? 'bg-emerald-500/20 text-emerald-600 border-emerald-500/40' : 'bg-rose-500/20 text-rose-600 border-rose-500/40'"
              >
                {{ isPositive(effect) ? 'Buff' : 'Ailment' }}
              </span>
            </div>
            <div class="flex items-center gap-2 mt-1.5">
              <span class="w-1.5 h-1.5 rounded-full" :class="isPositive(effect) ? 'bg-emerald-400' : 'bg-rose-400'"></span>
              <span class="tw-muted text-[11px] italic">Currently active effect</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ra { font-family: 'rpgawesome' !important; display: inline-block; line-height: 1; text-align: center; }
</style>
