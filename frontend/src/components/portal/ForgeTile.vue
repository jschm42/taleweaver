<script setup lang="ts">
defineProps<{
  title: string
  subtitle: string
  /** RGB triplet, e.g. "251 191 36". */
  accentRgb: string
  imageSrc?: string
  icon?: string
  disabled?: boolean
}>()

defineEmits<{
  (e: 'activate'): void
}>()
</script>

<template>
  <button
    type="button"
    class="forge-tile group w-full rounded-xl px-3 py-2 sm:py-2.5 flex items-center gap-3 text-left disabled:opacity-50 disabled:cursor-wait"
    :style="{ '--accent-rgb': accentRgb }"
    :disabled="disabled"
    @click="$emit('activate')"
  >
    <span class="forge-sigil w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center shrink-0 transition-transform duration-500 group-hover:rotate-[8deg] group-hover:scale-110">
      <img v-if="imageSrc" :src="imageSrc" alt="" class="w-6 h-6 sm:w-7 sm:h-7 object-contain" />
      <i v-else :class="['ra', icon]" class="text-lg sm:text-xl"></i>
    </span>
    <span class="min-w-0 flex-1">
      <span class="block font-fantasy font-bold text-sm sm:text-base text-white tracking-wide">{{ title }}</span>
      <span class="block text-[11px] sm:text-xs text-slate-400 leading-snug truncate">{{ subtitle }}</span>
    </span>
    <i class="ra ra-arrow-cluster hidden sm:block text-sm opacity-0 -translate-x-2 transition-all group-hover:opacity-80 group-hover:translate-x-0" :style="{ color: `rgb(${accentRgb})` }"></i>
  </button>
</template>
