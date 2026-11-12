<script setup lang="ts">
/**
 * ImmersiveStoryFeed — Comic story feed, one scene at a time
 *
 * Each scene is its own segment (see storyDividers.ts): entering another scene starts a new one,
 * and the pager browses earlier scenes. Within a scene the feed is endless: chapter changes are
 * thin dividers, and older messages of the scene load when the reader scrolls near the top
 * (useLoadOlderOnScroll). New content is followed down (useScrollToLatest).
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import type { ComicTurn } from '@/composables/useComicTurns'
import LicenseInfoBlock from '@/components/game/LicenseInfoBlock.vue'
import ImmersiveStoryExchange from '@/components/game/immersive/ImmersiveStoryExchange.vue'
import ThinkingIndicator from '@/components/game/immersive/ThinkingIndicator.vue'
import { Sparkles, ChevronLeft, ChevronRight, ChevronsDown, Compass, Loader2 } from 'lucide-vue-next'
import { useScrollToLatest } from './useScrollToLatest'
import { useLoadOlderOnScroll } from './useLoadOlderOnScroll'
import { chapterStartingAt, groupSceneSegments, segmentSceneLabel, type SceneSegment, type StoryDivider } from './storyDividers'
import ChapterBanner from './ChapterBanner.vue'
import AdventureEndingCard from './AdventureEndingCard.vue'
import type { SequenceDetail } from '@/types'

const props = defineProps<{
  pages: ComicTurn[]
  isEvaluating?: boolean
  statusText?: string
  sheet?: any
  entities: any[]
  currentSceneDescription?: string | null
  npcMetadata: Record<string, any>
  gameId?: string
  turnError?: { message: string; action: string } | null
  /** The server has older messages than the loaded ones. */
  hasOlderMessages?: boolean
  /** Loads and prepends the next older page of messages. */
  loadOlderMessages?: () => Promise<void>
  /** Scene id -> scene metadata (label) for the dividers. */
  sceneNodes?: Record<string, any>
  /** Sequence id -> title for the chapter banners. */
  sequenceTitles?: Record<string, string>
  /** Sequence id -> number and description for the chapter banners. */
  sequenceDetails?: Record<string, SequenceDetail>
}>()

const emit = defineEmits<{
  retryTurn: []
  cancelTurnError: []
  openSheet: []
  npcClick: [name: string]
  itemClick: [item: any]
  takeDirect: [item: any]
  npcHover: [entity: any, event: MouseEvent]
  npcLeave: []
  npcContextmenu: [entity: any, event: MouseEvent]
  backToMenu: []
  loadSave: []
}>()

const storyContainerRef = ref<HTMLElement | null>(null)
/** Key of the earlier scene the reader browses with the pager; null follows the latest scene. */
const viewingKey = ref<string | null>(null)
/** Wrapper of the inline panels after the newest exchange (choice dialog, container, unlock). */
const inlinePanelsRef = ref<HTMLElement | null>(null)

/** Gap (px) kept above the newest exchange when auto-follow stops at its start. */
const FOLLOW_TOP_GAP_PX = 8

function latestExchangeElement(): HTMLElement | undefined {
  const exchanges = storyContainerRef.value?.querySelectorAll<HTMLElement>('[data-story-exchange]')
  return exchanges?.[exchanges.length - 1]
}

// Follow new content (streamed narration, engine events, choice dialogs) down the feed, but
// never past the start of the newest exchange: a long narration stays readable from its top.
const { hasContentBelow, isFollowing, scrollToLatest, scrollToTop: scrollToContainerTop, resumeFollowing } = useScrollToLatest(storyContainerRef, {
  canFollow: () => viewingKey.value === null,
  maxFollowTop: () => {
    const latest = latestExchangeElement()
    const exchangeTop = latest ? Math.max(0, latest.offsetTop - FOLLOW_TOP_GAP_PX) : null
    const panelTop = inlinePanelsFollowTop()
    if (panelTop === null) return exchangeTop
    return exchangeTop === null ? panelTop : Math.max(exchangeTop, panelTop)
  },
})

// Older messages load only once the reader scrolled up themselves (auto-follow is off then),
// and only in the oldest loaded scene: an earlier scene starts above the top of any other one.
const { isLoadingOlder, loadOlder } = useLoadOlderOnScroll(storyContainerRef, {
  hasMore: () => Boolean(props.hasOlderMessages && props.loadOlderMessages && activeIndex.value === 0),
  load: () => props.loadOlderMessages?.() ?? Promise.resolve(),
  readerScrolled: () => !isFollowing.value,
})

// A short first window does not fill the feed: load more until it scrolls.
watch(() => props.pages.length, () => void loadOlder())

/**
 * Scroll position that shows the open inline panels completely, or their top when they are
 * taller than the feed; `null` while no panel is open.
 */
function inlinePanelsFollowTop(): number | null {
  const panels = inlinePanelsRef.value
  const container = storyContainerRef.value
  if (!panels || !container || panels.offsetHeight === 0) return null
  const reservedBottom = parseFloat(window.getComputedStyle(container).paddingBottom) || 0
  const panelTop = Math.max(0, panels.offsetTop - FOLLOW_TOP_GAP_PX)
  const panelBottom = panels.offsetTop + panels.offsetHeight + reservedBottom - container.clientHeight
  return Math.min(panelTop, Math.max(0, panelBottom))
}

// A panel that opens (or grows) below the narration is followed into view, even if the
// reader had scrolled up: it waits for their input.
let inlinePanelsHeight = 0
let inlinePanelsObserver: ResizeObserver | null = null
onMounted(() => {
  if (!inlinePanelsRef.value || typeof ResizeObserver === 'undefined') return
  inlinePanelsObserver = new ResizeObserver(() => {
    const height = inlinePanelsRef.value?.offsetHeight ?? 0
    if (height > inlinePanelsHeight) resumeFollowing()
    inlinePanelsHeight = height
  })
  inlinePanelsObserver.observe(inlinePanelsRef.value)
})
onBeforeUnmount(() => inlinePanelsObserver?.disconnect())

function scrollToLatestExchange() {
  showLatest()
  resumeFollowing()
  latestExchangeElement()?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

/** Render key of the newest exchange; prepending older pages does not change it. */
const latestExchangeKey = computed(() => {
  const page = props.pages[props.pages.length - 1]
  const exchange = page?.exchanges[page.exchanges.length - 1]
  return (exchange && exchangeKey(exchange)) || ''
})

// A new exchange at the end (usually the player's own action): follow again, even if the
// reader had scrolled up before. Older pages prepended at the top do not count.
watch(latestExchangeKey, (key, previousKey) => {
  if (key && previousKey && key !== previousKey && viewingKey.value === null) resumeFollowing()
})

// ── Scene segments & pager ──────────────────────────────────────────────────

const segments = computed<SceneSegment[]>(() => groupSceneSegments(props.pages))

/** Stable identity of a segment: its newest exchange (older pages only extend it at the top). */
function segmentKey(segment: SceneSegment | undefined): string {
  const page = segment?.pages[segment.pages.length - 1]
  const exchange = page?.exchanges[page.exchanges.length - 1]
  return (exchange && exchangeKey(exchange)) || `scene-${segment?.sceneId ?? 'legacy'}`
}

const activeIndex = computed(() => {
  const last = Math.max(0, segments.value.length - 1)
  if (viewingKey.value === null) return last
  const found = segments.value.findIndex((s) => segmentKey(s) === viewingKey.value)
  return found < 0 ? last : found
})

const activeSegment = computed(() => segments.value[activeIndex.value])
const activeSceneLabel = computed(() => segmentSceneLabel(activeSegment.value, props.sceneNodes || {}))
const isLatestSegment = computed(() => activeIndex.value >= segments.value.length - 1)
const hasPager = computed(() => segments.value.length > 1 || Boolean(props.hasOlderMessages))
const canGoBack = computed(() => activeIndex.value > 0 || Boolean(props.hasOlderMessages))

function scrollToTop() {
  nextTick(() => {
    scrollToContainerTop()
  })
}

function showSegment(index: number) {
  const target = segments.value[index]
  viewingKey.value = !target || index >= segments.value.length - 1 ? null : segmentKey(target)
  scrollToTop()
  if (viewingKey.value === null) resumeFollowing()
}

/** Earlier scene; loads older messages first while the oldest loaded scene may be incomplete. */
async function showPrevious() {
  const key = segmentKey(activeSegment.value)
  for (let guard = 0; activeIndex.value === 0 && props.hasOlderMessages && guard < 20; guard++) {
    if (!props.loadOlderMessages) break
    await props.loadOlderMessages()
    const index = segments.value.findIndex((s) => segmentKey(s) === key)
    if (index > 0) {
      viewingKey.value = key
      break
    }
  }
  if (activeIndex.value > 0) showSegment(activeIndex.value - 1)
}

/** Back to the latest scene, following new content again. */
function showLatest() {
  if (viewingKey.value === null) return
  showSegment(segments.value.length - 1)
}

// Entering another scene starts the new segment at its top (auto-follow then moves on).
// Watched at the end of the story only: older pages prepended at the top never count.
let latestSceneId: string | null | undefined
watch(latestExchangeKey, () => {
  const sceneId = segments.value[segments.value.length - 1]?.sceneId ?? null
  const entered = latestSceneId !== undefined && sceneId !== latestSceneId
  latestSceneId = sceneId
  if (entered && viewingKey.value === null) scrollToTop()
}, { immediate: true })

defineExpose({ scrollToLatestExchange, showLatest })

type Exchange = ComicTurn['exchanges'][number]

/** One flat row of the feed; keys stay stable when older pages are prepended. */
type FeedItem =
  | { kind: 'divider'; key: string; divider: StoryDivider }
  | { kind: 'chapter'; key: string; sequenceId: string }
  | { kind: 'license'; key: string; message: any }
  | { kind: 'ending'; key: string; message: any }
  | { kind: 'exchange'; key: string; exchange: Exchange }

function exchangeKey(exchange: Exchange): string | undefined {
  const first = exchange.userMessage || exchange.assistantMessage || exchange.systemMessages[0]
  return first?._key || first?.id
}

/** Position of each page in the whole loaded history (chapters can begin across scenes). */
const globalIndex = computed(() => new Map(props.pages.map((page, index) => [page, index])))

function chapterInfo(sequenceId: string): SequenceDetail {
  const detail = props.sequenceDetails?.[sequenceId]
  return detail ?? { title: props.sequenceTitles?.[sequenceId] || 'New chapter' }
}

const feedItems = computed<FeedItem[]>(() => {
  const items: FeedItem[] = []
  const pages = activeSegment.value?.pages ?? []
  pages.forEach((page, pageIdx) => {
    const firstKey = page.exchanges[0] ? exchangeKey(page.exchanges[0]) : undefined
    const index = globalIndex.value.get(page) ?? 0
    const isHistoryStart = index === 0 && !props.hasOlderMessages
    const chapter = chapterStartingAt(props.pages[index - 1], page, isHistoryStart)
    // Credits open the adventure; the first chapter follows them.
    if (page.licenseMessage) {
      items.push({ kind: 'license', key: `license-${page.licenseMessage._key ?? pageIdx}`, message: page.licenseMessage })
    }
    if (chapter) {
      items.push({ kind: 'chapter', key: `chapter-${chapter}-${firstKey ?? pageIdx}`, sequenceId: chapter })
    }
    const pushEndings = (afterExchange: number) => {
      page.endings
        .filter((ending) => ending.afterExchange === afterExchange)
        .forEach((ending, endIdx) => {
          const key = ending.message._key ?? ending.message.id ?? `p${pageIdx}-end${afterExchange}-${endIdx}`
          items.push({ kind: 'ending', key: `ending-${key}`, message: ending.message })
        })
    }
    pushEndings(0)
    page.exchanges.forEach((exchange, exIdx) => {
      items.push({ kind: 'exchange', key: exchangeKey(exchange) ?? `p${pageIdx}-e${exIdx}`, exchange })
      pushEndings(exIdx + 1)
    })
  })
  return items
})
</script>

<template>
  <div class="story-feed flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
    <div
      ref="storyContainerRef"
      class="comic-story-container tw-feed flex-1 overflow-y-auto tw-scroll p-2 sm:p-4 sm:pl-3.5 flex flex-col min-h-0 relative"
      :class="{ 'pb-12 sm:pb-12': hasPager }"
    >
      <!-- Empty State -->
      <div v-if="!props.pages.length && !props.isEvaluating" class="flex-1 flex flex-col items-center justify-center text-slate-500">
        <Sparkles class="w-8 h-8 text-amber-400/60 mb-2 animate-pulse" />
        <p class="text-sm font-semibold tracking-wider uppercase">Awaiting Adventure Turn...</p>
      </div>

      <!-- Loading / Scene Transitioning State -->
      <div v-else-if="!props.pages.length && props.isEvaluating" class="flex-1 flex flex-col items-center justify-center text-slate-400 my-auto">
        <div class="relative flex items-center justify-center w-12 h-12 mb-3">
          <div class="absolute inset-0 rounded-full bg-amber-400/20 animate-ping"></div>
          <Compass class="w-8 h-8 text-amber-400 animate-spin" style="animation-duration: 4s;" />
        </div>
        <p class="text-xs font-black uppercase tracking-widest text-amber-300 animate-pulse">
          {{ props.statusText || 'Arriving at new scene...' }}
        </p>
      </div>

      <template v-else>
        <!-- Earlier messages of this scene: load on scroll (only the oldest loaded scene can have more) -->
        <div v-if="props.hasOlderMessages && activeIndex === 0" class="story-feed-older" aria-live="polite">
          <Loader2 v-if="isLoadingOlder" class="w-4 h-4 animate-spin" />
          <span>{{ isLoadingOlder ? 'Loading earlier story…' : 'Scroll up for earlier story' }}</span>
        </div>

        <template v-for="item in feedItems" :key="item.key">
          <!-- SCENE / CHAPTER DIVIDER -->
          <div v-if="item.kind === 'divider'" class="story-feed-divider" role="separator">
            <span class="story-feed-divider-rule"></span>
            <span v-if="item.divider.chapter || item.divider.scene" class="story-feed-divider-label">
              <span v-if="item.divider.chapter" class="story-feed-divider-chapter">{{ item.divider.chapter }}</span>
              <span v-if="item.divider.chapter && item.divider.scene" aria-hidden="true"> · </span>
              <span v-if="item.divider.scene">{{ item.divider.scene }}</span>
            </span>
            <span class="story-feed-divider-rule"></span>
          </div>

          <!-- CHAPTER BANNER (a sequence begins) -->
          <ChapterBanner
            v-else-if="item.kind === 'chapter'"
            :title="chapterInfo(item.sequenceId).title"
            :order="chapterInfo(item.sequenceId).order"
            :description="chapterInfo(item.sequenceId).description"
            :dynamic="chapterInfo(item.sequenceId).dynamic"
          />

          <!-- LICENSE & CREDITS BANNER (start of the adventure) -->
          <LicenseInfoBlock v-else-if="item.kind === 'license'" :msg="item.message" class="shrink-0 max-w-2xl" />

          <!-- ENDING CARD (win / game over) -->
          <AdventureEndingCard
            v-else-if="item.kind === 'ending'"
            :content="item.message.content"
            @back-to-menu="emit('backToMenu')"
            @load-save="emit('loadSave')"
          />

          <ImmersiveStoryExchange
            v-else
            data-story-exchange
            class="shrink-0"
            :exchange="item.exchange"
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

        <!-- "GM is working" badge: always the last item of the feed, whatever the turn adds
             (player bubble, engine events, streamed narration) or hides (silent commands). -->
        <ThinkingIndicator
          v-if="props.isEvaluating && isLatestSegment"
          class="self-start my-1"
          :status-text="props.statusText"
        />
      </template>

      <!-- Inline content after the latest exchange (e.g. a pending choice dialog); hidden while browsing earlier scenes. -->
      <div ref="inlinePanelsRef" class="shrink-0 flex flex-col">
        <slot v-if="viewingKey === null" name="after-exchanges" />
      </div>
    </div>

    <!-- SCENE PAGER (revealed on hover; pinned while browsing an earlier scene) -->
    <div
      v-if="hasPager"
      class="tw-pager story-feed-pager absolute inset-x-0 bottom-0 z-20 flex items-center justify-between px-3 py-1.5 text-xs font-bold"
      :class="{ 'is-pinned': viewingKey !== null }"
    >
      <div class="flex items-center gap-1 min-w-0">
        <button
          type="button"
          :disabled="!canGoBack || isLoadingOlder"
          @click="showPrevious"
          class="tw-pager-button p-1 rounded disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          title="Previous scene"
        >
          <ChevronLeft class="w-3.5 h-3.5" />
        </button>
        <span class="px-2 truncate">{{ activeSceneLabel }}</span>
        <button
          type="button"
          :disabled="isLatestSegment"
          @click="showSegment(activeIndex + 1)"
          class="tw-pager-button p-1 rounded disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          title="Next scene"
        >
          <ChevronRight class="w-3.5 h-3.5" />
        </button>
      </div>

      <button
        v-if="viewingKey !== null"
        type="button"
        @click="showLatest"
        class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-black uppercase tracking-wider hover:bg-amber-500/30 cursor-pointer"
      >
        Jump to Latest
      </button>
    </div>

    <!-- Jump to the latest message (only while content is hidden below) -->
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

.story-feed-older {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.25rem 0 0.75rem;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.55;
}

.story-feed-divider {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1.25rem 0 0.75rem;
  color: var(--tw-accent-soft, #fbbf24);
}

.story-feed-divider-rule {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, currentColor 55%, transparent), transparent);
}

.story-feed-divider-label {
  max-width: 70%;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.story-feed-divider-chapter {
  font-weight: 900;
}
</style>
