<script setup lang="ts">
/**
 * ImmersiveStoryFeed — Comic story pages and page history
 *
 * A page covers one scene + sequence (chapter) and shows all of its exchanges in order
 * (see comicPages.ts). The page only changes when the scene or the sequence changes.
 */
import { ref, computed, watch, nextTick } from 'vue'
import type { ComicTurn } from '@/composables/useComicTurns'
import LicenseInfoBlock from '@/components/game/LicenseInfoBlock.vue'
import ImmersiveStoryExchange from '@/components/game/immersive/ImmersiveStoryExchange.vue'
import { Sparkles, ChevronLeft, ChevronRight, ChevronsDown, Compass } from 'lucide-vue-next'
import { useScrollToLatest } from './useScrollToLatest'

const props = defineProps<{
  gameTurns: ComicTurn[]
  activeTurn: ComicTurn | null
  activeTurnIndex: number
  viewingTurnIndex: number | null
  isEvaluating?: boolean
  statusText?: string
  sheet?: any
  entities: any[]
  currentSceneDescription?: string | null
  npcMetadata: Record<string, any>
  gameId?: string
  turnError?: { message: string; action: string } | null
}>()

const emit = defineEmits<{
  goToTurn: [index: number]
  goToLatestTurn: []
  retryTurn: []
  cancelTurnError: []
  openSheet: []
  npcClick: [name: string]
  itemClick: [item: any]
  takeDirect: [item: any]
  npcHover: [entity: any, event: MouseEvent]
  npcLeave: []
  npcContextmenu: [entity: any, event: MouseEvent]
}>()

const storyContainerRef = ref<HTMLElement | null>(null)
const { hasContentBelow, scrollToLatest } = useScrollToLatest(storyContainerRef)

// New page: start reading at the top.
watch(() => props.activeTurnIndex, () => {
  nextTick(() => {
    if (storyContainerRef.value) {
      storyContainerRef.value.scrollTop = 0
    }
  })
})

function scrollToLatestExchange() {
  const exchanges = storyContainerRef.value?.querySelectorAll('[data-story-exchange]')
  const latest = exchanges?.[exchanges.length - 1] as HTMLElement | undefined
  latest?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

// New exchange on the page being followed: scroll to its beginning.
watch(
  () => props.activeTurn?.exchanges.length ?? 0,
  (count, previousCount) => {
    if (props.viewingTurnIndex !== null || count <= previousCount) return
    nextTick(scrollToLatestExchange)
  }
)

defineExpose({ scrollToLatestExchange })

const hasPager = computed(() => props.gameTurns.length > 1)

function isLatestExchange(exIdx: number): boolean {
  const isLatestPage = props.activeTurnIndex >= props.gameTurns.length - 1
  return isLatestPage && exIdx === (props.activeTurn?.exchanges.length ?? 0) - 1
}
</script>

<template>
  <div class="story-feed flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
    <!-- COMIC STORY CONTAINER (Page Display) -->
    <div
      ref="storyContainerRef"
      class="comic-story-container tw-feed flex-1 overflow-y-auto tw-scroll p-2 sm:p-4 flex flex-col min-h-0 relative"
      :class="{ 'pb-12 sm:pb-12': hasPager }"
    >
      <!-- Empty State -->
      <div v-if="!props.activeTurn && !props.isEvaluating" class="flex-1 flex flex-col items-center justify-center text-slate-500">
        <Sparkles class="w-8 h-8 text-amber-400/60 mb-2 animate-pulse" />
        <p class="text-sm font-semibold tracking-wider uppercase">Awaiting Adventure Turn...</p>
      </div>

      <!-- Loading / Scene Transitioning State -->
      <div v-else-if="!props.activeTurn && props.isEvaluating" class="flex-1 flex flex-col items-center justify-center text-slate-400 my-auto">
        <div class="relative flex items-center justify-center w-12 h-12 mb-3">
          <div class="absolute inset-0 rounded-full bg-amber-400/20 animate-ping"></div>
          <Compass class="w-8 h-8 text-amber-400 animate-spin" style="animation-duration: 4s;" />
        </div>
        <p class="text-xs font-black uppercase tracking-widest text-amber-300 animate-pulse">
          {{ props.statusText || 'Arriving at new scene...' }}
        </p>
      </div>

      <template v-else-if="props.activeTurn">
        <!-- LICENSE & CREDITS BANNER (Initial Page / Re-run) -->
        <LicenseInfoBlock v-if="props.activeTurn.licenseMessage" :msg="props.activeTurn.licenseMessage" class="shrink-0 max-w-2xl" />

        <!-- EXCHANGES OF THIS SCENE -->
        <ImmersiveStoryExchange
          v-for="(exchange, exIdx) in props.activeTurn.exchanges"
          :key="exchange.userMessage?._key || exchange.assistantMessage?._key || exIdx"
          data-story-exchange
          class="shrink-0"
          :exchange="exchange"
          :is-latest="isLatestExchange(exIdx)"
          :is-evaluating="props.isEvaluating"
          :status-text="props.statusText"
          :sheet="props.sheet"
          :entities="props.entities"
          :current-scene-description="props.currentSceneDescription"
          :npc-metadata="props.npcMetadata"
          :game-id="props.gameId"
          :turn-error="props.turnError"
          @retry-turn="emit('retryTurn')"
          @cancel-turn-error="emit('cancelTurnError')"
          @open-sheet="emit('openSheet')"
          @npc-click="(name) => emit('npcClick', name)"
          @item-click="(item) => emit('itemClick', item)"
          @take-direct="(item) => emit('takeDirect', item)"
          @npc-hover="(entity, event) => emit('npcHover', entity, event)"
          @npc-leave="emit('npcLeave')"
          @npc-contextmenu="(entity, event) => emit('npcContextmenu', entity, event)"
        />
      </template>

      <!-- Inline content after the latest exchange (e.g. a pending choice dialog); hidden while browsing history. -->
      <slot v-if="props.viewingTurnIndex === null" name="after-exchanges" />
    </div>

    <!-- COMIC PAGE NAVIGATION & PAGING CONTROLS (revealed on hover; pinned while browsing history) -->
    <div
      v-if="hasPager"
      class="tw-pager story-feed-pager absolute inset-x-0 bottom-0 z-20 flex items-center justify-between px-3 py-1.5 text-xs font-bold"
      :class="{ 'is-pinned': props.viewingTurnIndex !== null }"
    >
      <div class="flex items-center gap-1">
        <button
          type="button"
          :disabled="props.activeTurnIndex <= 0"
          @click="emit('goToTurn', props.activeTurnIndex - 1)"
          class="tw-pager-button p-1 rounded disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          title="Previous Turn"
        >
          <ChevronLeft class="w-3.5 h-3.5" />
        </button>
        <span class="px-2 tabular-nums">Turn {{ props.activeTurnIndex + 1 }} / {{ props.gameTurns.length }}</span>
        <button
          type="button"
          :disabled="props.activeTurnIndex >= props.gameTurns.length - 1"
          @click="emit('goToTurn', props.activeTurnIndex + 1)"
          class="tw-pager-button p-1 rounded disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          title="Next Turn"
        >
          <ChevronRight class="w-3.5 h-3.5" />
        </button>
      </div>

      <button
        v-if="props.viewingTurnIndex !== null"
        type="button"
        @click="emit('goToLatestTurn')"
        class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-black uppercase tracking-wider hover:bg-amber-500/30 cursor-pointer"
      >
        Jump to Latest
      </button>
    </div>

    <!-- Jump to the latest message (only while content is hidden below; after the pager for the ~ selector) -->
    <Transition name="scroll-latest">
      <button
        v-if="hasContentBelow"
        type="button"
        class="tw-scroll-latest story-feed-scroll-latest absolute right-3 z-30"
        title="Jump to the latest message"
        aria-label="Jump to the latest message"
        @click="scrollToLatest"
      >
        <ChevronsDown class="w-5 h-5" />
      </button>
    </Transition>
  </div>
</template>

<style scoped>
.scroll-latest-enter-active,
.scroll-latest-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.scroll-latest-enter-from,
.scroll-latest-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.9);
}

.story-feed-scroll-latest {
  bottom: 0.75rem;
  transition: bottom 0.2s ease;
}

.story-feed-pager {
  opacity: 0;
  transform: translateY(100%);
  pointer-events: none;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.story-feed:hover .story-feed-pager,
.story-feed:focus-within .story-feed-pager,
.story-feed-pager.is-pinned {
  opacity: 1;
  transform: none;
  pointer-events: auto;
}

/* Keep the jump button clear of the pager whenever the pager is shown */
.story-feed:hover .story-feed-pager ~ .story-feed-scroll-latest,
.story-feed:focus-within .story-feed-pager ~ .story-feed-scroll-latest,
.story-feed-pager.is-pinned ~ .story-feed-scroll-latest {
  bottom: 3rem;
}

/* Touch devices cannot hover: always show the pager there */
@media (hover: none) {
  .story-feed-pager {
    opacity: 1;
    transform: none;
    pointer-events: auto;
  }

  .story-feed-pager ~ .story-feed-scroll-latest {
    bottom: 3rem;
  }
}

.comic-story-container > * {
  flex-shrink: 0;
}
</style>
