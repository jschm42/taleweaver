<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AdventureDownloadJob, AdventureLibraryItem } from '@/types/adventureLibrary'
import { isActiveJob } from '@/composables/useAdventureLibrary'
import { formatBytes } from '@/utils/editor_utils'

type BadgeTone = 'download' | 'installed' | 'update' | 'blocked' | 'progress'

const props = defineProps<{
  item: AdventureLibraryItem
  selected: boolean
  selectable: boolean
  job?: AdventureDownloadJob
}>()

const emit = defineEmits<{
  (e: 'toggle', id: string): void
  (e: 'cancel', jobId: string): void
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
  blocked: 'bg-white/5 text-slate-500 border-white/10',
  progress: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
}

const coverFailed = ref(false)
watch(
  () => props.item.entry.cover_url,
  () => (coverFailed.value = false),
)

const entry = computed(() => props.item.entry)
const showCover = computed(() => Boolean(entry.value.cover_url) && !coverFailed.value)
const activeJob = computed(() => (props.job && isActiveJob(props.job) ? props.job : null))

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

// Spec D10: tags/author/language are metadata on the card, never a filter control.
const MAX_VISIBLE_TAGS = 3
const visibleTags = computed(() => entry.value.tags.slice(0, MAX_VISIBLE_TAGS))
const extraTagCount = computed(() => Math.max(0, entry.value.tags.length - MAX_VISIBLE_TAGS))
const hasMetadata = computed(
  () => Boolean(entry.value.author || entry.value.language || entry.value.license),
)

function progressLabel(job: AdventureDownloadJob): string {
  if (job.state === 'queued') {
    return 'Queued'
  }
  if (job.state === 'verifying') {
    return 'Verifying'
  }
  if (job.state === 'importing') {
    return 'Importing'
  }
  const total = job.total_bytes || entry.value.size_bytes
  const percent = total > 0 ? Math.min(100, Math.floor((job.bytes_downloaded / total) * 100)) : 0
  return `Downloading ${percent}%`
}

const badge = computed<{ label: string; tone: BadgeTone }>(() => {
  if (activeJob.value) {
    return { label: progressLabel(activeJob.value), tone: 'progress' }
  }
  if (props.item.downloading) {
    return { label: 'Downloading', tone: 'progress' }
  }
  if (!props.item.compatible) {
    return { label: `Requires app >= ${props.item.requires_app_version ?? entry.value.min_app_version}`, tone: 'blocked' }
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
    class="relative flex flex-col rounded-xl border bg-white/5 overflow-hidden transition-colors"
    :class="[
      selected ? 'border-blue-500/60 ring-1 ring-blue-500/40' : 'border-white/10',
      selectable ? 'cursor-pointer hover:border-blue-500/30' : 'cursor-default',
    ]"
    @click="onCardClick"
  >
    <div class="relative aspect-[3/2] w-full bg-slate-800">
      <img
        v-if="showCover"
        :src="entry.cover_url ?? undefined"
        :alt="`Cover of ${entry.title}`"
        loading="lazy"
        class="w-full h-full object-cover"
        @error="coverFailed = true"
      />
      <div
        v-else
        class="w-full h-full flex flex-col items-center justify-center gap-1 bg-gradient-to-br px-4 text-center"
        :class="placeholderGradient"
        aria-hidden="true"
      >
        <span class="text-4xl font-black text-white/80 font-display tracking-tight">{{ initials }}</span>
        <span class="text-[10px] uppercase tracking-[0.2em] text-white/40 font-bold line-clamp-1">{{ entry.title }}</span>
      </div>

      <label
        class="absolute top-2 left-2 flex items-center justify-center w-8 h-8 rounded-lg bg-slate-950/70 border border-white/15"
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
    </div>

    <div class="p-4 flex flex-col gap-2 flex-1">
      <h4 class="text-sm font-black text-white leading-tight">{{ entry.title }}</h4>
      <p class="text-xs text-slate-400 leading-relaxed line-clamp-2">{{ entry.teaser }}</p>

      <div v-if="hasMetadata" class="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[10px] text-slate-500">
        <span v-if="entry.author" class="truncate max-w-[9rem]" :title="entry.author">{{ entry.author }}</span>
        <span v-if="entry.author && entry.language" class="text-slate-700" aria-hidden="true">·</span>
        <span v-if="entry.language" class="font-mono uppercase">{{ entry.language }}</span>
        <span
          v-if="entry.license"
          class="px-1.5 py-0.5 rounded border border-white/10 bg-white/5 font-mono"
        >{{ entry.license }}</span>
      </div>

      <div v-if="visibleTags.length" class="flex flex-wrap items-center gap-1">
        <span
          v-for="tag in visibleTags"
          :key="tag"
          class="px-1.5 py-0.5 rounded-full border border-white/10 bg-white/5 text-[10px] text-slate-400"
        >{{ tag }}</span>
        <span v-if="extraTagCount > 0" class="text-[10px] text-slate-500">+{{ extraTagCount }}</span>
      </div>

      <div class="mt-auto pt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500 font-mono">
        <span>v{{ entry.version }}</span>
        <span>{{ formatBytes(entry.size_bytes) }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="flex-1 text-center px-2 py-1.5 rounded-lg border text-[10px] font-black uppercase tracking-widest"
          :class="BADGE_CLASSES[badge.tone]"
        >
          {{ badge.label }}
        </span>
        <button
          v-if="activeJob"
          type="button"
          class="px-2 py-1.5 rounded-lg border border-white/15 text-slate-300 text-[10px] font-bold uppercase tracking-widest hover:bg-white/5 transition-colors"
          :aria-label="`Cancel download of ${entry.title}`"
          @click.stop="emit('cancel', activeJob.job_id)"
        >
          Cancel
        </button>
      </div>
    </div>
  </article>
</template>
