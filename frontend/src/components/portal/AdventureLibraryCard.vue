<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AdventureLibraryItem } from '@/types/adventureLibrary'
import { formatBytes } from '@/utils/editor_utils'

type BadgeTone = 'download' | 'installed' | 'update' | 'progress'

const props = defineProps<{
  item: AdventureLibraryItem
  selected: boolean
  selectable: boolean
  installing: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle', id: string): void
}>()

// Static class names so Tailwind keeps them; picked by a stable hash of the title.
const PLACEHOLDER_GRADIENTS = [
  'from-indigo-900 to-slate-900',
  'from-emerald-900 to-slate-900',
  'from-amber-900 to-slate-900',
  'from-rose-900 to-slate-900',
  'from-cyan-900 to-slate-900',
  'from-violet-900 to-slate-900',
]

const BADGE_CLASSES: Record<BadgeTone, string> = {
  download: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  installed: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  update: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  progress: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
}

const coverFailed = ref(false)
// Covers are generated at 2:3; older landscape covers sit at the top over a blurred copy.
const isLandscape = ref(false)
watch(
  () => props.item.cover_url,
  () => {
    coverFailed.value = false
    isLandscape.value = false
  },
)

function onCoverLoad(event: Event) {
  const img = event.target as HTMLImageElement
  isLandscape.value = img.naturalWidth > img.naturalHeight
}

const entry = computed(() => props.item.entry)
const showCover = computed(() => Boolean(props.item.cover_url) && !coverFailed.value)

const initials = computed(() =>
  entry.value.title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join(''),
)

const placeholderGradient = computed(() => {
  const hash = [...entry.value.title].reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) >>> 0, 7)
  return PLACEHOLDER_GRADIENTS[hash % PLACEHOLDER_GRADIENTS.length]
})

// Spec D10: author/language/license are metadata on the card, never a filter control.
const hasMetadata = computed(
  () => Boolean(entry.value.author || entry.value.language || entry.value.license),
)

const badge = computed<{ label: string; tone: BadgeTone }>(() => {
  if (props.installing) {
    return { label: 'Installing...', tone: 'progress' }
  }
  if (props.item.update_available) {
    return { label: `Update to ${entry.value.version}`, tone: 'update' }
  }
  if (props.item.installed_version) {
    return { label: 'Downloaded', tone: 'installed' }
  }
  return { label: 'Download', tone: 'download' }
})

function onCardClick() {
  if (!props.selectable) {
    return
  }
  emit('toggle', entry.value.id)
}
</script>

<template>
  <article
    class="group relative flex flex-col aspect-[3/4] rounded-xl border overflow-hidden bg-slate-950 shadow-[0_18px_40px_-18px_rgba(0,0,0,0.8)] transition-[border-color,box-shadow] duration-300"
    :class="[
      selected ? 'border-blue-500/70 ring-2 ring-blue-500/40' : 'border-white/10',
      selectable ? 'cursor-pointer hover:border-blue-400/40' : 'cursor-default',
    ]"
    @click="onCardClick"
  >
    <!-- Artwork: the cover fills the card and fades into the shade below the text. -->
    <div class="absolute inset-0 overflow-hidden" aria-hidden="true">
      <template v-if="showCover">
        <img
          v-if="isLandscape"
          :src="item.cover_url ?? undefined"
          alt=""
          class="absolute inset-0 w-full h-full object-cover scale-125 blur-2xl brightness-[0.45] saturate-150"
        />
        <img
          :src="item.cover_url ?? undefined"
          :alt="`Cover of ${entry.title}`"
          loading="lazy"
          class="w-full object-cover transition-transform duration-[1200ms] ease-out group-hover:scale-105"
          :class="isLandscape ? 'relative aspect-[3/2] tale-card__cover--landscape' : 'absolute inset-0 h-full object-[center_30%]'"
          @load="onCoverLoad"
          @error="coverFailed = true"
        />
      </template>
      <div
        v-else
        class="w-full h-full flex flex-col items-center justify-start gap-1 pt-[22%] bg-gradient-to-br px-4 text-center"
        :class="placeholderGradient"
      >
        <span class="text-5xl font-black text-white/80 font-display tracking-tight">{{ initials }}</span>
        <span class="text-[10px] uppercase tracking-[0.2em] text-white/40 font-bold line-clamp-1">{{ entry.title }}</span>
      </div>
      <div class="tale-card__shade absolute inset-0"></div>
    </div>

    <!-- Top row: selection and deprecated badge -->
    <div class="relative z-10 flex items-start justify-between gap-2 p-2">
      <label
        class="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-950/70 border border-white/15 backdrop-blur-md"
        :class="selectable ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'"
        @click.stop
      >
        <input
          type="checkbox"
          class="w-4 h-4 accent-blue-500"
          :checked="selected"
          :disabled="!selectable"
          :aria-label="`Select ${entry.title}`"
          @change="emit('toggle', entry.id)"
        />
      </label>

      <span
        v-if="entry.deprecated"
        class="px-2 py-1 rounded-md border border-amber-500/40 bg-slate-950/80 text-amber-300 text-[10px] font-black uppercase tracking-widest backdrop-blur-md"
        :title="entry.format_version
          ? `Made with adventure format ${entry.format_version} (below 1.3.1). It can still be installed and played.`
          : 'This adventure no longer meets the current standard. It can still be installed and played.'"
      >
        Deprecated
      </span>
    </div>

    <!-- Bottom: text over the shade -->
    <div class="tale-legible relative z-10 mt-auto p-4 flex flex-col gap-2">
      <h4 class="text-base font-black text-white leading-tight line-clamp-2">{{ entry.title }}</h4>
      <p class="text-xs text-slate-300/90 leading-relaxed line-clamp-3">{{ entry.teaser }}</p>

      <div v-if="hasMetadata" class="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[10px] text-slate-400">
        <span v-if="entry.author" class="truncate max-w-[9rem]" :title="entry.author">{{ entry.author }}</span>
        <span v-if="entry.author && entry.language" class="text-slate-600" aria-hidden="true">·</span>
        <span v-if="entry.language" class="font-mono uppercase">{{ entry.language }}</span>
        <span
          v-if="entry.license"
          class="px-1.5 py-0.5 rounded border border-white/10 bg-black/30 font-mono"
        >{{ entry.license }}</span>
      </div>

      <div class="flex items-center justify-between gap-2 text-[11px] text-slate-400 font-mono">
        <span>v{{ entry.version }}</span>
        <span>{{ formatBytes(entry.size_bytes) }}</span>
      </div>
      <span
        class="text-center px-2 py-1.5 rounded-lg border text-[10px] font-black uppercase tracking-widest backdrop-blur-md"
        :class="BADGE_CLASSES[badge.tone]"
      >
        {{ badge.label }}
      </span>
    </div>
  </article>
</template>
