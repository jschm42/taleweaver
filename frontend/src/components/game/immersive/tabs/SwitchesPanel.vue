<script setup lang="ts">
/**
 * SwitchesPanel — Switches of the current scene as picture tiles with their state badge.
 * Clicking a tile flips the switch.
 */
import { ref } from 'vue'
import { getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import { switchState, switchStateId } from '../switchState'

const props = defineProps<{
  switches: any[]
  isEvaluating?: boolean
}>()

const emit = defineEmits<{
  switchFlip: [entity: any]
}>()

const thumbFailed = ref<Record<string, boolean>>({})
const brokenImages = ref<Record<string, boolean>>({})

function imageUrl(path: string): string {
  return thumbFailed.value[path] ? getOriginalImageUrl(path) : getImageUrl(path, { thumbnail: true })
}

function onImageError(path: string) {
  if (!thumbFailed.value[path]) {
    thumbFailed.value[path] = true
    return
  }
  brokenImages.value[path] = true
}

function hasImage(sw: any): boolean {
  return Boolean(sw.image_url) && !brokenImages.value[sw.image_url]
}

/** ON-like states get the accent badge; everything else reads as idle. */
function isActive(sw: any): boolean {
  return ['ON', 'OPEN', 'ACTIVE', 'UP', 'TRUE'].includes(switchStateId(sw))
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <h3 class="tw-panel-title">Switches</h3>

    <div class="grid grid-cols-3 gap-2">
      <button
        v-for="sw in props.switches"
        :key="sw.id"
        type="button"
        class="tw-card tw-card--interactive group relative flex flex-col items-center gap-1 p-1.5 pt-2 text-center"
        :class="{ 'opacity-50 pointer-events-none': props.isEvaluating }"
        :disabled="props.isEvaluating"
        :title="`Toggle ${sw.name}`"
        :aria-label="`Toggle ${sw.name}, currently ${switchState(sw)}`"
        @click="emit('switchFlip', sw)"
      >
        <span
          class="absolute top-1 right-1 z-10 rounded-md border px-1 py-px text-[9px] font-black uppercase tracking-wider"
          :class="isActive(sw) ? 'border-emerald-500/50 bg-emerald-500/20 text-emerald-300' : 'border-white/15 bg-slate-950/80 text-slate-300'"
        >
          {{ switchState(sw) }}
        </span>

        <span class="relative w-14 h-14 rounded-xl overflow-hidden bg-slate-950/90 border border-white/10 flex items-center justify-center shrink-0 shadow-inner group-hover:scale-105 transition-transform">
          <img
            v-if="hasImage(sw)"
            :src="imageUrl(sw.image_url)"
            :alt="sw.name"
            decoding="async"
            class="w-full h-full object-cover"
            @error="onImageError(sw.image_url)"
          />
          <i v-else class="ra ra-lever text-3xl text-amber-300/80"></i>
        </span>

        <span class="text-[11px] font-bold leading-snug line-clamp-2">{{ sw.name }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
