<script setup lang="ts">
import { computed } from 'vue'
import { STORY_IDEA_MAX_LENGTH } from '@/constants/storyIdeaLimits'

const props = defineProps<{ value: string }>()

const length = computed(() => props.value.length)
const isOver = computed(() => length.value > STORY_IDEA_MAX_LENGTH)
const isNear = computed(() => !isOver.value && length.value > STORY_IDEA_MAX_LENGTH * 0.9)
const colorClass = computed(() => {
  if (isOver.value) {
    return 'text-red-400'
  }
  if (isNear.value) {
    return 'text-amber-400'
  }
  return 'text-white/35'
})
</script>

<template>
  <p :class="['mt-1 text-[10px] uppercase tracking-widest text-right', colorClass]">
    <span v-if="isOver">Too long, shorten by {{ (length - STORY_IDEA_MAX_LENGTH).toLocaleString('en-US') }} characters · </span>
    {{ length.toLocaleString('en-US') }} / {{ STORY_IDEA_MAX_LENGTH.toLocaleString('en-US') }} characters
  </p>
</template>
