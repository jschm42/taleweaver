<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { AdventureTemplateSummary } from '@/types'
import { X, Play } from 'lucide-vue-next'
import LicenseInfoPopup from '@/components/common/LicenseInfoPopup.vue'
import AdventureCardMenu, { type AdventureCardAction } from './AdventureCardMenu.vue'
import TaleCardArtwork from './TaleCardArtwork.vue'
import { useCardTilt } from '@/composables/useCardTilt'
import { resolveGenreAccent, toneToLabel } from '@/composables/useGenreAccent'
import { setAmbientAccent } from '@/store/portalAmbient'
import { formatRelative } from '@/utils/relativeTime'

const props = defineProps<{
  template: AdventureTemplateSummary
  isStartingSession?: boolean
  isStartingThisTemplate?: boolean
  isUpdating?: boolean
  /** Only cards on the "In Progress" shelf continue a session; archive cards always begin a new one. */
  resumable?: boolean
}>()

const emit = defineEmits<{
  (e: 'startSession', templateId: string): void
  (e: 'resumeSession', gameId: string): void
  (e: 'updateAdventure', templateId: string): void
  (e: 'migrate', template: AdventureTemplateSummary): void
  (e: 'cover', templateId: string): void
  (e: 'edit', templateId: string): void
  (e: 'duplicate', templateId: string): void
  (e: 'exportAdz', templateId: string, title: string): void
  (e: 'exportAdv', templateId: string, title: string): void
  (e: 'delete', templateId: string, title: string): void
  (e: 'dismissWarning', templateId: string): void
}>()

const isMenuOpen = ref(false)
const isLicenseOpen = ref(false)
const licenseTriggerRef = ref<HTMLElement | null>(null)
const bursts = ref<Array<{ id: number; x: string; y: string }>>([])

const { tiltRef, onPointerMove, onPointerLeave } = useCardTilt()

const toneLabel = computed(() => toneToLabel(props.template.selected_tone))
const accent = computed(() => resolveGenreAccent(toneLabel.value))
const needsMigration = computed(() => !!(props.template.is_legacy_format || !props.template.can_start))
const DEPRECATED_HINT = 'Made with an older adventure format (below 1.3.1). It can still be played; '
  + 'crafting recipes from older versions may not work.'
const hasLicenseInfo = computed(() =>
  !!(props.template.license || props.template.creator || props.template.copyright || props.template.license_url)
)
const resumeGameId = computed(() =>
  props.resumable && props.template.has_active_session ? props.template.active_game_id || null : null
)
const teaser = computed(() => (props.template.teaser || '').replace(/\\n/g, '\n'))

const actionHandlers: Record<AdventureCardAction, () => void> = {
  cover: () => emit('cover', props.template.template_id),
  migrate: () => emit('migrate', props.template),
  edit: () => emit('edit', props.template.template_id),
  duplicate: () => emit('duplicate', props.template.template_id),
  adz: () => emit('exportAdz', props.template.template_id, props.template.title),
  adv: () => emit('exportAdv', props.template.template_id, props.template.title),
  delete: () => emit('delete', props.template.template_id, props.template.title),
  update: () => emit('updateAdventure', props.template.template_id),
}

function openLicenseInfo(): void {
  nextTick(() => {
    isLicenseOpen.value = true
  })
}

function onEnter(): void {
  setAmbientAccent(accent.value.rgb)
}

// The ambient tint is deliberately kept on leave: resetting it would flicker while moving between cards.
function onLeave(): void {
  onPointerLeave()
}

/** Spawns an ink burst at the click position, then continues or starts the session. */
function primaryAction(event: MouseEvent): void {
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const id = Date.now()
  bursts.value.push({ id, x: `${event.clientX - rect.left}px`, y: `${event.clientY - rect.top}px` })
  window.setTimeout(() => {
    bursts.value = bursts.value.filter((b) => b.id !== id)
  }, 700)
  if (resumeGameId.value) {
    emit('resumeSession', resumeGameId.value)
    return
  }
  emit('startSession', props.template.template_id)
}
</script>

<template>
  <article
    ref="tiltRef"
    class="tale-card group rounded-2xl aspect-[3/4] flex flex-col"
    :class="isMenuOpen || isLicenseOpen ? 'z-30' : 'z-0'"
    :style="{ '--accent-rgb': accent.rgb }"
    @pointerenter="onEnter"
    @pointermove="onPointerMove"
    @pointerleave="onLeave"
  >
    <TaleCardArtwork :image-url="props.template.image_url" :accent="accent" />

    <!-- Top row: status badges + options -->
    <!-- z-20: its menu and popups overlap the bottom block, which must stay underneath -->
    <div class="relative z-20 flex items-start justify-between gap-2 p-2 sm:p-3">
      <div class="flex flex-col gap-1.5 items-start min-w-0">
        <span
          v-if="toneLabel"
          class="tale-chip tale-hover-fade px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-full text-[9px] sm:text-[11px] font-bold tracking-wide flex items-center gap-1.5 max-w-full"
          :title="toneLabel"
        >
          <i :class="['ra', accent.icon]" class="text-[10px] sm:text-xs"></i>
          <span class="truncate">{{ toneLabel }}</span>
        </span>
        <button
          v-if="props.template.has_update"
          @click.stop="emit('updateAdventure', props.template.template_id)"
          :disabled="props.isUpdating"
          class="px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full bg-slate-950/80 hover:bg-cyan-950/90 text-cyan-200 text-[9px] sm:text-[11px] font-bold border border-cyan-400/50 flex items-center gap-1.5 backdrop-blur-md transition-all disabled:opacity-50"
          :title="`Update available${props.template.available_version ? ': v' + props.template.available_version : ''}. Click to update this adventure.`"
        >
          <i :class="props.isUpdating ? 'ra ra-cycle animate-spin' : 'ra ra-recycle'" class="text-[10px] sm:text-xs"></i>
          <span>{{ props.isUpdating ? 'Updating...' : (props.template.available_version ? `Update v${props.template.available_version}` : 'Update') }}</span>
        </button>
        <span
          v-if="props.template.is_deprecated && !needsMigration"
          class="px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full bg-slate-950/80 text-amber-300 text-[9px] sm:text-[11px] font-black uppercase tracking-widest border border-amber-500/40 backdrop-blur-md"
          :title="DEPRECATED_HINT"
        >
          Deprecated
        </span>
        <div
          v-if="props.template.creation_error"
          class="group/warn relative px-2 py-0.5 sm:py-1 rounded-full bg-slate-950/80 text-amber-300 text-[9px] sm:text-[11px] font-bold border border-amber-500/30 flex items-center gap-1.5 backdrop-blur-md cursor-help"
        >
          <i class="ra ra-help text-[10px] sm:text-xs"></i>
          <span class="hidden sm:inline">Visual issues</span>
          <button @click.stop="emit('dismissWarning', props.template.template_id)" class="p-0.5 hover:bg-amber-500/20 rounded-md" title="Dismiss notice">
            <X class="w-2.5 h-2.5 sm:w-3 sm:h-3" />
          </button>
          <div class="absolute left-0 top-full mt-2 w-64 p-3 rounded-xl bg-slate-900/95 border border-amber-500/30 text-[11px] text-slate-300 leading-relaxed shadow-2xl opacity-0 group-hover/warn:opacity-100 transition-opacity pointer-events-none z-40">
            <div class="text-amber-400 font-bold mb-1">Generation note</div>
            {{ props.template.creation_error }}
          </div>
        </div>
      </div>

      <!-- Managing an adventure happens in the archive; the "In Progress" shelf only continues it. -->
      <AdventureCardMenu
        v-if="!props.resumable"
        v-model:open="isMenuOpen"
        :needs-migration="needsMigration"
        :has-update="!!props.template.has_update"
        :is-updating="props.isUpdating"
        @select="(action) => actionHandlers[action]()"
        @license="openLicenseInfo"
      />
    </div>

    <!-- Bottom: title, meta, teaser, action -->
    <div class="tale-legible relative z-10 mt-auto p-2.5 sm:p-4 lg:p-5 flex flex-col gap-1.5 sm:gap-2.5">
      <div
        v-if="props.template.has_active_session"
        class="flex items-center gap-1.5 text-[10px] sm:text-[11px] font-bold text-slate-200"
      >
        <i class="ra ra-hourglass tale-accent-text"></i>
        <span class="truncate">Played {{ formatRelative(props.template.last_played_at) }}{{ props.template.current_scene_name ? ` · ${props.template.current_scene_name}` : '' }}</span>
      </div>

      <h3 class="tale-title text-[13px] sm:text-lg lg:text-xl text-white leading-tight line-clamp-2 break-words">
        {{ props.template.title }}
      </h3>

      <div class="tale-hover-reveal hidden sm:grid">
        <div class="flex items-center gap-2 text-[10px] text-slate-400">
          <span v-if="props.template.version" class="px-1.5 py-px rounded border border-white/10 bg-black/30 font-mono">v{{ props.template.version }}</span>
          <button
            v-if="hasLicenseInfo"
            ref="licenseTriggerRef"
            @click.stop="isLicenseOpen = !isLicenseOpen"
            class="ml-auto text-emerald-400/70 hover:text-emerald-300 transition-colors"
            :title="`License: ${props.template.license || 'View details'}`"
            aria-label="View license & credits"
          >
            <i class="ra ra-scroll-unfurled text-xs"></i>
          </button>
        </div>
      </div>

      <div v-if="teaser" class="tale-reveal hidden sm:grid">
        <p class="font-narrative text-[13px] leading-snug text-slate-300/90 line-clamp-4 whitespace-pre-wrap">{{ teaser }}</p>
      </div>

      <button
        v-if="needsMigration && props.template.has_update"
        class="w-full py-2 sm:py-3 rounded-xl text-[10px] sm:text-xs font-bold tracking-wider uppercase border flex items-center justify-center gap-2 bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 border-cyan-500/40 transition-all"
        :disabled="props.isUpdating"
        @click="emit('updateAdventure', props.template.template_id)"
      >
        <i :class="props.isUpdating ? 'ra ra-cycle animate-spin' : 'ra ra-recycle'"></i>
        <span class="truncate">{{ props.isUpdating ? 'Updating...' : 'Update to play' }}</span>
      </button>

      <button
        v-else-if="needsMigration"
        class="w-full py-2 sm:py-3 rounded-xl text-[10px] sm:text-xs font-bold tracking-wider uppercase border flex items-center justify-center gap-2 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 border-amber-500/40 transition-all"
        title="Migrate this adventure to the current format"
        @click.stop="emit('migrate', props.template)"
      >
        <i class="ra ra-wrench"></i>
        <span class="truncate">Migrate adventure</span>
      </button>

      <div v-else class="tale-hover-reveal grid">
        <div>
          <button
            class="tale-action w-full min-w-0 py-2 sm:py-3 rounded-xl text-[10px] sm:text-xs font-bold tracking-wider uppercase flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="props.isStartingSession"
            @click="primaryAction"
          >
            <span v-for="b in bursts" :key="b.id" class="ink-burst" :style="{ '--burst-x': b.x, '--burst-y': b.y }"></span>
            <i v-if="props.isStartingSession" class="ra ra-cycle animate-spin"></i>
            <Play v-else class="w-3.5 h-3.5 fill-current" />
            <span class="truncate">{{ props.isStartingThisTemplate ? 'Starting...' : (resumeGameId ? 'Continue' : 'Begin') }}</span>
          </button>
        </div>
      </div>
    </div>

    <LicenseInfoPopup
      v-model:open="isLicenseOpen"
      :license="props.template.license"
      :license-url="props.template.license_url"
      :creator="props.template.creator"
      :copyright="props.template.copyright"
      :anchor-el="licenseTriggerRef"
      accent="emerald"
    />
  </article>
</template>
