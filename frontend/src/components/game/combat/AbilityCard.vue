<script setup lang="ts">
import { Lock } from 'lucide-vue-next'

defineProps<{
  icon: string
  typeLine: string
  title: string
  cost: string
  check: string
  effects: string
  footer: string
  /** Category color (hex) used for the card frame, art and cost pip. */
  tone: string
  disabled: boolean
  locked?: boolean
}>()

const emit = defineEmits<{
  use: []
  hover: [event: MouseEvent]
  leave: []
}>()
</script>

<template>
  <!-- Trading-card layout: name bar with cost, art, type line, rules text, target line. -->
  <button
    type="button"
    class="tw-ability-card"
    :class="{ 'is-disabled': disabled }"
    :style="{ '--ability-tone': tone }"
    :disabled="disabled"
    :aria-label="`${title}, ${cost}, ${footer}`"
    @click="emit('use')"
    @mouseenter="emit('hover', $event)"
    @mousemove="emit('hover', $event)"
    @mouseleave="emit('leave')"
  >
    <span class="tw-ability-name">
      <span class="truncate">{{ title }}</span>
      <span class="tw-ability-cost">{{ cost }}</span>
    </span>
    <span class="tw-ability-art">
      <Lock v-if="locked" class="w-8 h-8" />
      <i v-else :class="['ra', icon]"></i>
    </span>
    <span class="tw-ability-type">{{ typeLine }}</span>
    <span class="tw-ability-text">
      <span class="block font-mono truncate">{{ check }}</span>
      <span class="block truncate" :title="effects">{{ effects }}</span>
    </span>
    <span class="tw-ability-footer truncate">{{ footer }}</span>
  </button>
</template>
