<script setup lang="ts">
import { computed } from 'vue'
import type { CombatState } from '@/types'

const props = defineProps<{
  combat: CombatState
}>()

const chips = computed(() => {
  const enemies = new Map((props.combat.enemies ?? []).map((e) => [e.id, e]))
  return (props.combat.initiative ?? []).map((entry, idx) => {
    const enemy = enemies.get(entry.id)
    return {
      ...entry,
      isPlayer: entry.id === 'PLAYER',
      isActive: props.combat.active && props.combat.active_actor === entry.id,
      isDone: idx < (props.combat.turn_index ?? 0),
      isOut: !!(enemy && (enemy.defeated || enemy.fled)),
    }
  })
})
</script>

<template>
  <ol v-if="chips.length" class="flex items-center gap-1.5 overflow-x-auto overflow-y-hidden py-1 px-1 max-w-full initiative-track" aria-label="Initiative order">
    <li
      v-for="(chip, idx) in chips"
      :key="chip.id"
      class="flex items-center gap-1.5 shrink-0"
    >
      <span v-if="idx > 0" class="text-amber-500/40 text-xs">›</span>
      <span
        class="flex items-center gap-1.5 px-2 py-1 rounded-full border text-xs font-bold transition-all"
        :class="[
          chip.isActive
            ? 'border-amber-300 bg-amber-500/20 text-amber-100 shadow-[0_0_12px_rgba(251,191,36,0.45)] scale-105'
            : chip.isPlayer
              ? 'border-emerald-500/40 bg-emerald-950/40 text-emerald-200'
              : 'border-rose-500/30 bg-rose-950/30 text-rose-200',
          chip.isDone && !chip.isActive ? 'opacity-50' : '',
          chip.isOut ? 'line-through opacity-40' : '',
        ]"
        :title="`d20 ${chip.roll} + ${chip.bonus} = ${chip.total}`"
      >
        <i :class="['ra text-[10px]', chip.isPlayer ? 'ra-player' : 'ra-monster-skull']"></i>
        <span class="max-w-24 truncate">{{ chip.isPlayer ? 'You' : chip.name }}</span>
        <span class="font-mono text-[10px] text-amber-300/80">{{ chip.total }}</span>
      </span>
    </li>
  </ol>
</template>

<style scoped>
.initiative-track {
  scrollbar-width: thin;
  scrollbar-color: rgba(251, 191, 36, 0.25) transparent;
}
</style>
