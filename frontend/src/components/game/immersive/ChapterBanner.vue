<script setup lang="ts">
/**
 * ChapterBanner — the start of a sequence/chapter, shown inline in the story feed.
 *
 * Replaces the former full-screen title band: it marks the chapter where it begins in the
 * story, so nothing has to be clicked away. Colors and fonts follow the active dialog skin
 * (the same --tw-overlay-* tokens the band used).
 */
import { formatEntityRefs } from '@/utils/entityRefs'

const props = defineProps<{
  title: string
  order?: number | null
  description?: string | null
  /** Dynamic progression: chapters have no fixed number. */
  dynamic?: boolean
}>()
</script>

<template>
  <!-- Same width and alignment as the narration bubbles (w-full max-w-2xl, left). -->
  <section class="chapter-banner tw-overlay-band relative overflow-hidden shrink-0 self-start w-full max-w-2xl my-5 sm:my-7 rounded-2xl px-4 py-6 sm:py-7 text-center select-none" role="separator" :aria-label="`Chapter: ${props.title}`">
    <div class="tw-overlay-wash absolute inset-0 pointer-events-none opacity-40"></div>
    <div class="tw-overlay-texture absolute inset-0 pointer-events-none"></div>
    <div class="tw-overlay-glow absolute left-1/2 top-1/2 w-56 h-56 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl pointer-events-none"></div>

    <div class="relative z-10 flex flex-col items-center">
      <div class="flex items-center gap-3 mb-2">
        <span class="tw-overlay-rule w-8 sm:w-14 h-px"></span>
        <span class="tw-overlay-eyebrow text-[10px] sm:text-[11px] font-bold tracking-[0.35em] uppercase">
          <template v-if="!props.dynamic && props.order">Chapter {{ props.order }}</template>
          <template v-else>New Chapter</template>
        </span>
        <span class="tw-overlay-rule w-8 sm:w-14 h-px"></span>
      </div>

      <h2 class="chapter-banner-title tw-overlay-title tw-overlay-title--chapter text-xl sm:text-3xl font-black leading-tight">
        {{ props.title }}
      </h2>

      <div class="flex items-center justify-center gap-2 my-2.5 w-full">
        <span class="tw-overlay-rule w-14 sm:w-24 h-px"></span>
        <span class="tw-overlay-diamond w-1.5 h-1.5 rotate-45"></span>
        <span class="tw-overlay-rule w-14 sm:w-24 h-px"></span>
      </div>

      <p
        v-if="props.description"
        class="tw-overlay-muted text-xs sm:text-sm font-serif italic max-w-lg leading-relaxed"
        v-html="formatEntityRefs(props.description)"
      ></p>
    </div>
  </section>
</template>

<style scoped>
/* The in-feed banner uses the band's colors, but as a contained card. */
.chapter-banner {
  border-inline: 1px solid color-mix(in srgb, var(--tw-overlay-accent) 20%, transparent);
  animation: chapter-banner-in 0.9s cubic-bezier(0.16, 1, 0.3, 1) both;
}

.chapter-banner-title {
  letter-spacing: 0.1em;
  overflow-wrap: anywhere;
}

@keyframes chapter-banner-in {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
    filter: blur(2px);
  }
  to {
    opacity: 1;
    transform: none;
    filter: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chapter-banner {
    animation: none;
  }
}
</style>
