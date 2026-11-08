<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { playerAvatarUrl } from './leaderboardUtils'

const props = defineProps<{
  username: string
  imageUrl?: string | null
  sizeClass?: string
}>()

const hasError = ref(false)

watch(
  () => props.imageUrl,
  () => {
    hasError.value = false
  },
)

const src = computed(() => playerAvatarUrl(props.imageUrl, props.username))
const initial = computed(() => (props.username || '?').charAt(0).toUpperCase())
</script>

<template>
  <div
    class="relative shrink-0 rounded-full overflow-hidden bg-gradient-to-br from-aether-surface-bright to-aether-background border border-white/10"
    :class="props.sizeClass || 'w-10 h-10'"
  >
    <img
      v-if="src && !hasError"
      :src="src"
      :alt="props.username"
      class="w-full h-full object-cover"
      loading="lazy"
      @error="hasError = true"
    />
    <div v-else class="w-full h-full flex items-center justify-center font-fantasy font-bold text-amber-100/80 select-none">
      <span class="text-[0.9em]">{{ initial }}</span>
    </div>
  </div>
</template>
