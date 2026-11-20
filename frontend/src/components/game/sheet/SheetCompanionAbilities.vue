<script setup lang="ts">
/**
 * SheetCompanionAbilities — the companion's abilities (its special actions from the editor)
 * with a switch each: switched-off abilities are never used in combat.
 */
import type { CompanionAbility } from '@/types'

const props = defineProps<{
  abilities: CompanionAbility[]
  companionName: string
}>()

const emit = defineEmits<{
  command: [cmd: string]
}>()

function toggle(ability: CompanionAbility): void {
  emit('command', `/companion_ability ${ability.id} ${ability.enabled ? 'off' : 'on'}`)
}

const costLabel = (ability: CompanionAbility): string =>
  ability.cost ? `${ability.cost} ${ability.cost_type === 'mana' ? 'Mana' : 'Stamina'}` : 'Free'
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between gap-2">
      <h4 class="tw-panel-title tw-muted">Abilities in combat</h4>
      <span class="tw-muted text-xxs sm:text-xs">{{ props.abilities.filter((a) => a.enabled).length }} / {{ props.abilities.length }} active</span>
    </div>

    <p v-if="!props.abilities.length" class="tw-muted text-sm">
      {{ props.companionName }} has no special abilities. They are defined on the NPC in the adventure editor (Combat tab).
    </p>

    <button
      v-for="ability in props.abilities"
      :key="ability.id"
      type="button"
      role="switch"
      :aria-checked="ability.enabled"
      class="tw-card flex items-start gap-3 p-3 text-left transition-opacity"
      :class="{ 'opacity-60': !ability.enabled }"
      :title="ability.enabled ? 'Click to stop using this ability in combat' : 'Click to use this ability in combat'"
      @click="toggle(ability)"
    >
      <span
        class="mt-0.5 w-10 h-6 rounded-full relative shrink-0 transition-colors"
        :class="ability.enabled ? 'bg-sky-600' : 'bg-slate-600'"
      >
        <span
          class="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform"
          :class="ability.enabled ? 'translate-x-[1.125rem]' : 'translate-x-0.5'"
        ></span>
      </span>
      <span class="min-w-0 flex flex-col gap-0.5">
        <span class="tw-dialog-title text-sm sm:text-base">{{ ability.name }}</span>
        <span class="tw-muted text-[11px] uppercase tracking-wider">{{ ability.category }} · {{ costLabel(ability) }}</span>
        <span v-if="ability.description" class="text-xs sm:text-sm">{{ ability.description }}</span>
      </span>
    </button>

    <p class="tw-muted text-xxs">
      In combat {{ props.companionName }} uses active abilities on its own: healing when badly hurt, the others now and then.
      Area abilities are not used by companions yet.
    </p>
  </div>
</template>
