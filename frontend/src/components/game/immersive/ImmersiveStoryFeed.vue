<script setup lang="ts">
/**
 * ImmersiveStoryFeed — Endless comic story feed
 *
 * Shows the whole loaded story in one stream. Scene and chapter changes are marked with a thin
 * divider (see storyDividers.ts) instead of a new page. Older messages load when the reader
 * scrolls near the top (useLoadOlderOnScroll); new content is followed down (useScrollToLatest).
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import type { ComicTurn } from '@/composables/useComicTurns'
import LicenseInfoBlock from '@/components/game/LicenseInfoBlock.vue'
import ImmersiveStoryExchange from '@/components/game/immersive/ImmersiveStoryExchange.vue'
import ThinkingIndicator from '@/components/game/immersive/ThinkingIndicator.vue'
import { Sparkles, ChevronsDown, Compass, Loader2 } from 'lucide-vue-next'
import { useScrollToLatest } from './useScrollToLatest'
import { useLoadOlderOnScroll } from './useLoadOlderOnScroll'
import { dividerBefore, type StoryDivider } from './storyDividers'

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
  /** Sequence id -> title for the chapter dividers. */
  sequenceTitles?: Record<string, string>
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
}>()

const storyContainerRef = ref<HTMLElement | null>(null)
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
const { hasContentBelow, isFollowing, scrollToLatest, resumeFollowing } = useScrollToLatest(storyContainerRef, {
  maxFollowTop: () => {
    const latest = latestExchangeElement()
    const exchangeTop = latest ? Math.max(0, latest.offsetTop - FOLLOW_TOP_GAP_PX) : null
    const panelTop = inlinePanelsFollowTop()
    if (panelTop === null) return exchangeTop
    return exchangeTop === null ? panelTop : Math.max(exchangeTop, panelTop)
  },
})

// Older messages load only once the reader scrolled up themselves (auto-follow is off then).
const { isLoadingOlder, loadOlder } = useLoadOlderOnScroll(storyContainerRef, {
  hasMore: () => Boolean(props.hasOlderMessages && props.loadOlderMessages),
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
  resumeFollowing()
  latestExchangeElement()?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

/** Render key of the newest exchange; prepending older pages does not change it. */
const latestExchangeKey = computed(() => {
  const page = props.pages[props.pages.length - 1]
  const exchange = page?.exchanges[page.exchanges.length - 1]
  return exchange?.userMessage?._key || exchange?.assistantMessage?._key || ''
})

// A new exchange at the end (usually the player's own action): follow again, even if the
// reader had scrolled up before. Older pages prepended at the top do not count.
watch(latestExchangeKey, (key, previousKey) => {
  if (key && previousKey && key !== previousKey) resumeFollowing()
})

defineExpose({ scrollToLatestExchange })

type Exchange = ComicTurn['exchanges'][number]

/** One flat row of the feed; keys stay stable when older pages are prepended. */
type FeedItem =
  | { kind: 'divider'; key: string; divider: StoryDivider }
  | { kind: 'license'; key: string; message: any }
  | { kind: 'exchange'; key: string; exchange: Exchange }

function exchangeKey(exchange: Exchange): string | undefined {
  const first = exchange.userMessage || exchange.assistantMessage || exchange.systemMessages[0]
  return first?._key || first?.id
}

const feedItems = computed<FeedItem[]>(() => {
  const items: FeedItem[] = []
  props.pages.forEach((page, pageIdx) => {
    const firstKey = page.exchanges[0] ? exchangeKey(page.exchanges[0]) : undefined
    const divider = dividerBefore(props.pages[pageIdx - 1], page, props.sceneNodes || {}, props.sequenceTitles || {})
    if (divider) items.push({ kind: 'divider', key: `divider-${firstKey ?? pageIdx}`, divider })
    if (page.licenseMessage) {
      items.push({ kind: 'license', key: `license-${page.licenseMessage._key ?? pageIdx}`, message: page.licenseMessage })
    }
    page.exchanges.forEach((exchange, exIdx) => {
      items.push({ kind: 'exchange', key: exchangeKey(exchange) ?? `p${pageIdx}-e${exIdx}`, exchange })
    })
  })
  return items
})
</script>

<template>
  <div class="story-feed flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
    <div
      ref="storyContainerRef"
      class="comic-story-container tw-feed flex-1 overflow-y-auto tw-scroll p-2 sm:p-4 flex flex-col min-h-0 relative"
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
        <!-- Older history: loads on scroll; the hint shows while a page is on its way -->
        <div v-if="props.hasOlderMessages" class="story-feed-older" aria-live="polite">
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

          <!-- LICENSE & CREDITS BANNER (start of the adventure) -->
          <LicenseInfoBlock v-else-if="item.kind === 'license'" :msg="item.message" class="shrink-0 max-w-2xl" />

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
          v-if="props.isEvaluating"
          class="self-start my-1"
          :status-text="props.statusText"
        />
      </template>

      <!-- Inline content after the latest exchange (e.g. a pending choice dialog). -->
      <div ref="inlinePanelsRef" class="shrink-0 flex flex-col">
        <slot name="after-exchanges" />
      </div>
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
