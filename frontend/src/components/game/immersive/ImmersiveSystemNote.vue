<script setup lang="ts">
/**
 * ImmersiveSystemNote — Compact, skinned one-liner for an engine event (dice roll, item,
 * stat or quest change) inside the story feed. Die rolls get a tumbling die graphic.
 * Long texts render as a card. The full list lives in the System tab.
 */
import { computed, type Component } from 'vue'
import { Dices, Package, HeartPulse, ScrollText, Award, Info } from 'lucide-vue-next'
import { renderFormattedHtml } from '@/composables/useComicTurns'
import { cleanSystemContent, systemNoteKind, type SystemNoteKind } from './systemMessages'
import DiceBadge from './dice/DiceBadge.vue'
import { parseDiceRoll, stripDiceEmoji } from './dice/diceRolls'

const props = defineProps<{
  msg: { content: string; is_debug?: boolean }
}>()

const NOTE_ICONS: Record<SystemNoteKind, Component> = {
  dice: Dices,
  item: Package,
  vitals: HeartPulse,
  quest: ScrollText,
  reward: Award,
  info: Info,
}

const content = computed(() => cleanSystemContent(props.msg))
const roll = computed(() => parseDiceRoll(content.value))
const kind = computed<SystemNoteKind>(() => (roll.value ? 'dice' : systemNoteKind(content.value)))
// Multi-line or long text (e.g. the opening scene) does not fit the one-line pill shape.
const BLOCK_NOTE_MIN_LENGTH = 140
const isBlock = computed(
  () => !roll.value && (content.value.includes('\n') || content.value.length > BLOCK_NOTE_MIN_LENGTH)
)
const html = computed(() => renderFormattedHtml(roll.value ? stripDiceEmoji(content.value) : content.value))
</script>

<template>
  <div
    class="tw-sysnote shrink-0 self-start max-w-2xl animate-note-in"
    :class="{ 'tw-sysnote--roll': roll, 'tw-sysnote--block': isBlock }"
    :data-kind="kind"
    role="note"
  >
    <DiceBadge
      v-if="roll"
      :value="roll.value"
      :sides="roll.sides"
      :is-crit="roll.isCrit"
      :is-fumble="roll.isFumble"
    />
    <component :is="NOTE_ICONS[kind]" v-else class="tw-sysnote-icon shrink-0" aria-hidden="true" />
    <span class="tw-sysnote-text min-w-0" v-html="html"></span>
  </div>
</template>

<style scoped>
.animate-note-in {
  animation: noteIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes noteIn {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
