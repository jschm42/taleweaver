<script setup lang="ts">
/**
 * Featured adventure, shown at the top of the library while no session is in progress
 * (running sessions appear in ContinueRow). The full 2:3 cover sits next to the text.
 */
import { computed } from 'vue'
import type { AdventureTemplateSummary } from '@/types'
import { resolveGenreAccent, toneToLabel } from '@/composables/useGenreAccent'

const props = defineProps<{
  templates: AdventureTemplateSummary[]
  isStartingSession?: boolean
}>()

const emit = defineEmits<{
  (e: 'start-session', templateId: string): void
}>()

/** The first playable adventure with cover art. */
const featured = computed(() =>
  props.templates.find((t) => t.image_url && t.can_start !== false && !t.is_legacy_format) || null
)

const accent = computed(() => resolveGenreAccent(toneToLabel(featured.value?.selected_tone)))
const teaser = computed(() => (featured.value?.teaser || '').replace(/\\n/g, '\n'))
</script>

<template>
  <section
    v-if="featured"
    class="tale-enter relative overflow-hidden rounded-3xl"
    :style="{ '--accent-rgb': accent.rgb, boxShadow: `0 0 0 1px rgb(251 191 36 / 0.16), 0 30px 60px -30px rgb(${accent.rgb} / 0.45)` }"
    aria-labelledby="featured-heading"
  >
    <div class="absolute inset-0 bg-[#050b14]"></div>
    <img :src="featured.image_url || ''" alt="" aria-hidden="true" class="hero-ambient absolute inset-0 h-full w-full object-cover" />
    <div class="absolute inset-0" :style="{ background: `radial-gradient(ellipse at 100% 100%, rgb(${accent.rgb} / 0.22), transparent 55%)` }"></div>
    <div class="tale-card__frame absolute inset-0"><div class="tale-card__frame-bl"></div></div>

    <div class="relative z-10 flex items-center gap-4 p-4 sm:gap-6 sm:p-6">
      <div class="continue-cover aspect-[2/3] w-28 shrink-0 overflow-hidden rounded-lg sm:w-40">
        <img :src="featured.image_url || ''" :alt="`Cover of ${featured.title}`" class="hero-kenburns h-full w-full object-cover" />
      </div>
      <div class="min-w-0 max-w-2xl space-y-2 sm:space-y-3">
        <p class="tale-accent-text tale-legible text-[11px] font-bold uppercase tracking-[0.25em] sm:text-xs">
          <i class="ra ra-castle-emblem mr-1.5"></i>Featured tale
        </p>
        <h2 id="featured-heading" class="tale-title text-xl leading-tight text-white sm:text-3xl lg:text-4xl">{{ featured.title }}</h2>
        <p v-if="teaser" class="font-narrative text-sm leading-relaxed text-slate-300 line-clamp-3 whitespace-pre-wrap sm:text-base">{{ teaser }}</p>
        <div class="pt-1">
          <button
            type="button"
            class="tale-action tale-action--solid flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50 sm:px-6 sm:py-2.5 sm:text-sm"
            :disabled="isStartingSession"
            @click="emit('start-session', featured.template_id)"
          >
            <i class="ra ra-quill-ink"></i>Begin adventure
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
