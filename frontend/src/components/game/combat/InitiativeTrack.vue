<script setup lang="ts">
import { computed } from 'vue'
import type { CombatState } from '@/types'
import { getImageUrl, hasRenderableImagePath } from '@/utils/game_icons'

const props = defineProps<{
  combat: CombatState
  selectedTargetId?: string | null
  /** Fallback portrait for the protagonist when the combat snapshot has none. */
  playerImage?: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

function portrait(raw: string | null | undefined): string | null {
  return hasRenderableImagePath(raw) ? getImageUrl(raw as string) : null
}

/** Portraits in acting order for the current round. */
const slots = computed(() => {
  const enemies = new Map((props.combat.enemies ?? []).map((e) => [e.id, e]))
  return (props.combat.initiative ?? []).map((entry, idx) => {
    const enemy = enemies.get(entry.id)
    const isPlayer = entry.id === 'PLAYER'
    const isOut = !!(enemy && (enemy.defeated || enemy.fled))
    return {
      ...entry,
      isPlayer,
      isOut,
      selectable: !isPlayer && !isOut,
      image: portrait(isPlayer ? props.combat.player?.image_url || props.playerImage : enemy?.image_url),
      isActive: props.combat.active && props.combat.active_actor === entry.id,
      isDone: idx < (props.combat.turn_index ?? 0),
      isTarget: entry.id === props.selectedTargetId,
    }
  })
})

function slotTitle(slot: (typeof slots.value)[number]): string {
  const name = slot.isPlayer ? 'You' : slot.name
  const hint = slot.selectable ? ' · click to target' : ''
  return `${name}: d20 ${slot.roll} + ${slot.bonus} = ${slot.total}${hint}`
}
</script>

<template>
  <ol v-if="slots.length" class="tw-initiative" aria-label="Initiative order">
    <li v-for="(slot, idx) in slots" :key="slot.id" class="flex items-center gap-1.5 shrink-0">
      <span v-if="idx > 0" class="tw-initiative-arrow" aria-hidden="true">›</span>
      <component
        :is="slot.selectable ? 'button' : 'span'"
        :type="slot.selectable ? 'button' : undefined"
        class="tw-initiative-slot"
        :class="{
          'is-player': slot.isPlayer,
          'is-active': slot.isActive,
          'is-done': slot.isDone && !slot.isActive,
          'is-out': slot.isOut,
          'is-target': slot.isTarget && !slot.isOut,
        }"
        :title="slotTitle(slot)"
        :aria-label="slotTitle(slot)"
        :aria-pressed="slot.selectable ? slot.isTarget : undefined"
        @click="slot.selectable && emit('select', slot.id)"
      >
        <span class="tw-initiative-portrait">
          <img v-if="slot.image" :src="slot.image" :alt="slot.isPlayer ? 'You' : slot.name" class="w-full h-full object-cover">
          <i v-else :class="['ra text-3xl', slot.isPlayer ? 'ra-player' : 'ra-monster-skull']"></i>
          <span class="tw-initiative-total">{{ slot.total }}</span>
        </span>
        <span class="tw-initiative-name">{{ slot.isPlayer ? 'You' : slot.name }}</span>
      </component>
    </li>
  </ol>
</template>
