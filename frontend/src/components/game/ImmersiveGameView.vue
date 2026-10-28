<script setup lang="ts">
/**
 * ImmersiveGameView — Aesthetic Comic-Style RPG View
 *
 * Immersive full-scene view orchestrating:
 * - Full-screen scene background with atmospheric overlays
 * - Top header with scene details, tracked quest, clock, and speech controls
 * - Left character stage with portrait cards and active speaker auras
 * - Center story area with tabs (Story, Passages, Discoveries, System) and scene switches;
 *   the Story tab holds the comic feed (dialogue bubbles, narration boxes, turn history)
 * - Dialog skin (data-skin) resolved from player preference, adventure theme and tone
 * - Bottom action bar and user input with speech-to-text voice recording
 * - "story-end" slot rendered after the latest exchange (e.g. an inline choice dialog)
 */
import { ref, computed, toRef, watch, nextTick } from 'vue'
import type { ChatMessage } from '@/types'
import type { ConnectionStatus } from '@/composables/useGameSocket'
import { getImageUrl } from '@/utils/game_icons'
import { useComicTurns } from '@/composables/useComicTurns'
import ImmersiveHeader from './immersive/ImmersiveHeader.vue'
import ImmersiveCharacterStage from './immersive/ImmersiveCharacterStage.vue'
import ImmersiveStoryTabs from './immersive/ImmersiveStoryTabs.vue'
import StoryTabPanel from './immersive/tabs/StoryTabPanel.vue'
import SceneImageViewer from './immersive/SceneImageViewer.vue'
import { Image as ImageIcon } from 'lucide-vue-next'
import HoverRevealHeader from './immersive/HoverRevealHeader.vue'
import SpeechControls from './immersive/SpeechControls.vue'
import ImmersiveStoryFeed from './immersive/ImmersiveStoryFeed.vue'
import ImmersiveActionBar from './immersive/ImmersiveActionBar.vue'
import ImmersiveInputBar from './immersive/ImmersiveInputBar.vue'
import SceneTransitionOverlay from './immersive/SceneTransitionOverlay.vue'
import CinematicSequenceOverlay from './immersive/CinematicSequenceOverlay.vue'
import PlayAgentPanel from './immersive/PlayAgentPanel.vue'
import SceneSidebar from './immersive/SceneSidebar.vue'
import { useMediaQuery } from '@/composables/useMediaQuery'
import { useSceneSidebar } from '@/skins/useSceneSidebar'
import type { SettingsTabId } from './settings/types'
import { useStoryTabs } from './immersive/tabs/useStoryTabs'
import { useGameShortcuts } from './immersive/useGameShortcuts'
import { useTextDensity } from '@/skins/useTextDensity'
import { useTextScale } from '@/skins/useTextScale'
import { useSheetSkin } from '@/skins/useSheetSkin'

const props = defineProps<{
  messages: ChatMessage[]
  status: ConnectionStatus
  npcMetadata: Record<string, any>
  entities: any[]
  inventory: any[]
  sceneExits: any[]
  sceneSwitches: any[]
  items: any[]
  trackedQuest?: any
  statusText?: string
  showDebugLog?: boolean
  debugLogs?: { timestamp: string; content: string }[]
  inventoryGlow?: boolean
  mapGlow?: boolean
  questGlow?: boolean
  activeActionId?: string | null
  mode?: 'rpg' | 'story' | 'chat'
  inputLocked?: boolean
  sheet?: any
  gameId?: string
  currentSceneImage?: string | null
  adventureImage?: string | null
  currentSceneName?: string | null
  currentSceneDescription?: string | null
  promptSuggestions?: string[]
  exp?: number
  gameTime?: { dateShort: string; time: string } | null
  clockTick?: boolean
  isCheckpointSaving?: boolean
  exitTraversalBusy?: string
  isSceneTransitioning?: boolean
  sceneTransitionTarget?: {
    label: string
    targetSceneName: string
    targetSceneId?: string
    targetSceneImage?: string | null
  } | null
  exitUnlockBusy?: boolean
  turnError?: { message: string; action: string } | null
  worldMemories?: any[]
  activeSequence?: any | null
  adventureTitle?: string | null
  /** A choice dialog or unlock prompt waits for the player at the end of the story feed. */
  hasInlinePrompt?: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
  retryTurn: []
  cancelTurnError: []
  openSheet: []
  openMap: []
  openQuests: []
  openChronicles: []
  openMemories: []
  openSettings: [tab?: SettingsTabId]
  openDebug: []
  openWalkthrough: []
  npcHover: [entityOrName: any, event: MouseEvent]
  npcLeave: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  takeDirect: [entity: any]
  npcContextmenu: [entity: any, event: MouseEvent]
  itemContextmenu: [item: any, event: MouseEvent]
  selectAction: [actionId: string | null]
  npcClick: [name: string]
  itemClick: [item: any]
  traverseExit: [exit: any]
  switchFlip: [entity: any]
  exitSession: []
}>()

// --- State: Scene Image & Fallbacks ---
const brokenImages = ref<Record<string, boolean>>({})
const handleImageError = (path?: string | null) => {
  if (!path) return
  brokenImages.value[path] = true
}
const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}

const activeSceneImageUrl = computed(() => {
  if (props.currentSceneImage && showImage(props.currentSceneImage)) {
    return getImageUrl(props.currentSceneImage)
  }
  if (props.adventureImage && showImage(props.adventureImage)) {
    return getImageUrl(props.adventureImage)
  }
  return null
})

// Full-screen view of the scene artwork (opened from the header).
const showSceneImage = ref(false)

const transitionSceneImageUrl = computed(() => {
  const path = props.sceneTransitionTarget?.targetSceneImage
  if (path && showImage(path)) return getImageUrl(path)
  // Narrative-driven transitions: the scene_transition event already applied the new scene image.
  if (props.isSceneTransitioning && props.currentSceneImage && showImage(props.currentSceneImage)) {
    return getImageUrl(props.currentSceneImage)
  }
  return null
})

// --- State: Turn Evaluation & Input Blocking ---
const isEvaluating = computed(() => {
  return props.status === 'connecting' || props.status === 'loading' || !!props.inputLocked
})

// Keep the action buttons visible while one of them glows for new content.
const actionBarPinned = computed(() => Boolean(props.inventoryGlow || props.mapGlow || props.questGlow))

const canSendInput = computed(() => {
  return (
    (props.status === 'connected' || props.status === 'completed') &&
    !props.inputLocked &&
    !isEvaluating.value &&
    !props.sheet?.agent_active
  )
})

// --- Comic Turns Composable ---
const {
  gameTurns,
  activeTurnIndex,
  activeTurn,
  viewingTurnIndex,
  activeSpeakers,
  npcs,
  goToTurn,
  goToLatestTurn,
  getEntityForHover,
} = useComicTurns({
  messages: toRef(props, 'messages'),
  entities: toRef(props, 'entities'),
  npcMetadata: toRef(props, 'npcMetadata'),
  sheet: toRef(props, 'sheet'),
})

// --- Dialog skin ---
const { textDensity } = useTextDensity()
const { textScale } = useTextScale()
const { activeSkin, skinStyle } = useSheetSkin(() => props.sheet)

// --- Story tabs ---
// Wide screens show passages, discoveries and switches in a right-hand column (unless turned off in
// the settings); narrower ones keep them in the tab bar.
const isWideScreen = useMediaQuery('(min-width: 1280px)')
const { sceneSidebarEnabled } = useSceneSidebar()
const sidebarDocked = computed(() => isWideScreen.value && sceneSidebarEnabled.value)
const {
  activeStoryTab,
  sceneExits,
  sceneItems,
  systemLog,
  hasLockedExits,
  unseenSystem,
  unseenItems,
  systemSeenAtOpen,
  showStory,
} = useStoryTabs({
  sceneExits: () => (Array.isArray(props.sceneExits) ? props.sceneExits : []),
  items: () => (Array.isArray(props.items) ? props.items : []),
  systemMessages: computed(() => gameTurns.value.flatMap((turn) => turn.systemMessages)),
  docked: () => sidebarDocked.value,
})

// Any action that starts a turn (item click, context menu, take) shows its outcome in the story.
// A turn in flight is status 'connecting' ('loading' is only the initial session load).
watch(() => props.status, (status, previous) => {
  if (status !== 'connecting' || previous === 'connecting') return
  showStory()
  goToLatestTurn()
})

// Choice dialogs and unlock prompts are answered inline in the story feed, so bring the latest story page into view.
watch(() => props.hasInlinePrompt, (pending) => {
  if (!pending) return
  showStory()
  goToLatestTurn()
})

function handleTraverseExit(exit: any) {
  showStory()
  emit('traverseExit', exit)
}

// Input Bar Template Ref
const inputBarRef = ref<InstanceType<typeof ImmersiveInputBar> | null>(null)

const storyFeedRef = ref<InstanceType<typeof ImmersiveStoryFeed> | null>(null)

useGameShortcuts({
  scrollToLatestMessage: () => {
    showStory()
    goToLatestTurn()
    // Wait for a page switch to render (and reset its scroll) before jumping.
    void nextTick(() => requestAnimationFrame(() => storyFeedRef.value?.scrollToLatestExchange()))
  },
  focusInput: () => inputBarRef.value?.focus(),
})

function handleSend(content: string) {
  showStory()
  emit('send', content)
  goToLatestTurn()
}

function handleNpcClick(npc: any) {
  if (npc.id === 'PLAYER') {
    emit('openSheet')
  } else {
    if (!canSendInput.value) return
    emit('npcClick', npc.name)
    inputBarRef.value?.setInputText(`/say to ${npc.name}: `)
  }
}

function handleSuggestionSelect(suggestion: string) {
  inputBarRef.value?.setInputText(suggestion)
}

function handleSuggestionShuffle() {
  emit('send', '/shuffle')
}

defineExpose({
  setInputText: (text: string) => {
    inputBarRef.value?.setInputText(text)
  },
  appendText: (text: string) => {
    inputBarRef.value?.appendText(text)
  },
  toggleSayPrefix: () => {
    inputBarRef.value?.toggleSayPrefix()
  },
})
</script>

<template>
  <div
    class="tw-skin relative w-full h-full flex flex-col justify-between overflow-hidden select-none bg-slate-950 font-sans"
    :data-skin="activeSkin"
    :data-density="textDensity"
    :style="[skinStyle, { '--tw-text-scale': textScale }]"
  >
    <!-- 1. FULL VIEW SCENE BACKGROUND -->
    <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none">
      <img
        v-if="activeSceneImageUrl"
        :src="activeSceneImageUrl"
        class="tw-scene-image w-full h-full object-cover object-center scale-[1.01] transition-all duration-1000"
        alt="Scene background"
        @error="handleImageError(props.currentSceneImage || props.adventureImage)"
      />
      <div v-else class="w-full h-full bg-gradient-to-b from-slate-900 via-slate-950 to-black"></div>

      <!-- Atmospheric overlays -->
      <div class="absolute inset-0 bg-black/20"></div>
      <div class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-transparent to-slate-950/40"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-slate-950/60 via-transparent to-slate-950/40"></div>
      <div class="tw-scene-tint"></div>
    </div>

    <!-- 2. TOP ATMOSPHERIC HEADER BAR (shown on hover unless pinned) -->
    <HoverRevealHeader>
      <ImmersiveHeader
        :scene-name="props.currentSceneName || props.sheet?.current_scene"
        :active-sequence="props.activeSequence"
        :adventure-title="props.sheet?.adventure_title"
        :creator="props.sheet?.creator"
        :copyright="props.sheet?.copyright"
        :tracked-quest="props.trackedQuest"
        :game-time="props.gameTime"
        :clock-tick="props.clockTick"
        :exp="props.exp"
        :mode="props.mode"
        :debug-mode="!!props.sheet?.debug_mode"
        @open-chronicles="emit('openChronicles')"
        @open-quests="emit('openQuests')"
        @open-memories="emit('openMemories')"
        @open-settings="(tab?: SettingsTabId) => emit('openSettings', tab)"
        @open-debug="emit('openDebug')"
        @exit-session="emit('exitSession')"
      />
    </HoverRevealHeader>

    <!-- 3. MAIN INTERACTIVE STAGE AREA -->
    <div class="relative z-10 flex-grow min-h-0 flex flex-row gap-2 sm:gap-4 p-2 sm:p-4 lg:p-6 overflow-hidden">
      <!-- 3A. LEFT / CHARACTER STAGE -->
      <ImmersiveCharacterStage
        :npcs="npcs"
        :active-speakers="activeSpeakers"
        :active-turn-index="activeTurnIndex"
        @npc-click="handleNpcClick"
        @npc-hover="(npc, event) => emit('npcHover', getEntityForHover(npc), event)"
        @npc-leave="emit('npcLeave')"
        @npc-contextmenu="(npc, event) => emit('npcContextmenu', npc, event)"
      />

      <!-- 3B. CENTER / STORY AREA WITH SCENE HOTSPOTS & COMIC FEED -->
      <main class="flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
        <!-- Full scene artwork (top-right corner of the story area) -->
        <!-- Wrapper owns the positioning: .tw-tab sets position: relative on the button itself. -->
        <!-- z-[35]: above the story tabs (z-30, full width, rendered later), below the sequence overlay (z-[70]). -->
        <div v-if="activeSceneImageUrl" class="absolute right-0 top-0 z-[35]">
          <button
            type="button"
            class="tw-tab tw-scene-image-button"
            title="View the full scene image"
            aria-label="View the full scene image"
            @click="showSceneImage = true"
          >
            <ImageIcon class="w-5 h-5" />
          </button>
        </div>

        <ImmersiveStoryTabs
          v-model="activeStoryTab"
          :class="{ 'pr-14': activeSceneImageUrl }"
          :exit-count="sceneExits.length"
          :has-locked-exits="hasLockedExits"
          :item-count="sceneItems.length"
          :unseen-items="unseenItems"
          :system-count="systemLog.length"
          :unseen-system="unseenSystem"
          :scene-switches="props.sceneSwitches || []"
          :is-evaluating="isEvaluating"
          :docked="sidebarDocked"
          @switch-flip="(sw) => emit('switchFlip', sw)"
        />

        <StoryTabPanel
          v-if="activeStoryTab !== 'story'"
          :tab="activeStoryTab"
          :scene-exits="sceneExits"
          :items="sceneItems"
          :system-messages="systemLog"
          :system-seen-count="systemSeenAtOpen"
          :current-scene-name="props.currentSceneName || props.sheet?.current_scene"
          :is-evaluating="isEvaluating"
          :turn-error="props.turnError"
          @traverse-exit="handleTraverseExit"
          @item-click="(item) => emit('itemClick', item)"
          @item-hover="(item, event) => emit('itemHover', item, event)"
          @item-leave="emit('itemLeave')"
          @item-contextmenu="(item, event) => emit('itemContextmenu', item, event)"
          @take-direct="(item) => emit('takeDirect', item)"
        />

        <ImmersiveStoryFeed
          ref="storyFeedRef"
          v-show="activeStoryTab === 'story'"
          :game-turns="gameTurns"
          :active-turn="activeTurn"
          :active-turn-index="activeTurnIndex"
          :viewing-turn-index="viewingTurnIndex"
          :is-evaluating="isEvaluating"
          :status-text="props.statusText"
          :sheet="props.sheet"
          :entities="props.entities"
          :current-scene-description="props.currentSceneDescription"
          :npc-metadata="props.npcMetadata"
          :game-id="props.gameId"
          :turn-error="props.turnError"
          @go-to-turn="goToTurn"
          @go-to-latest-turn="goToLatestTurn"
          @retry-turn="emit('retryTurn')"
          @cancel-turn-error="emit('cancelTurnError')"
          @open-sheet="emit('openSheet')"
          @npc-click="(name) => handleNpcClick({ name })"
          @item-click="(item) => emit('itemClick', item)"
          @take-direct="(item) => emit('takeDirect', item)"
          @npc-hover="(entity, event) => emit('npcHover', entity, event)"
          @npc-leave="emit('npcLeave')"
          @npc-contextmenu="(entity, event) => emit('npcContextmenu', entity, event)"
        >
          <template #after-exchanges>
            <slot name="story-end" />
          </template>
        </ImmersiveStoryFeed>
      </main>

      <!-- 3C. RIGHT / SCENE SIDEBAR (wide screens) -->
      <SceneSidebar
        v-if="sidebarDocked"
        :scene-exits="sceneExits"
        :items="sceneItems"
        :scene-switches="props.sceneSwitches || []"
        :current-scene-name="props.currentSceneName || props.sheet?.current_scene"
        :is-evaluating="isEvaluating"
        @switch-flip="(sw) => emit('switchFlip', sw)"
        @traverse-exit="handleTraverseExit"
        @item-click="(item) => emit('itemClick', item)"
        @item-hover="(item, event) => emit('itemHover', item, event)"
        @item-leave="emit('itemLeave')"
        @item-contextmenu="(item, event) => emit('itemContextmenu', item, event)"
        @take-direct="(item) => emit('takeDirect', item)"
      />

      <!-- 3D. RIGHT / PLAY-AGENT CONTROL PANEL -->
      <PlayAgentPanel v-if="props.sheet?.agent_active" />
    </div>

    <!-- 4. BOTTOM ACTION BAR & USER INPUT -->
    <footer class="tw-footer relative z-20 flex flex-col bg-slate-950/95 backdrop-blur-xl border-t border-slate-800/90 shadow-[0_-10px_30px_rgba(0,0,0,0.8)] shrink-0">
      <!-- Speech playback controls float centered above the footer while something is read aloud
           (the right corner belongs to the story feed's "scroll to latest" button). -->
      <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 z-30 max-w-[calc(100%-1.5rem)]">
        <SpeechControls />
      </div>

      <!-- Action buttons slide in when the pointer is over the footer (always shown on touch). -->
      <div class="tw-action-reveal" :class="{ 'is-pinned': actionBarPinned }">
        <ImmersiveActionBar
          :inventory="props.inventory"
          :tracked-quest="props.trackedQuest"
          :inventory-glow="props.inventoryGlow"
          :map-glow="props.mapGlow"
          :quest-glow="props.questGlow"
          :prompt-suggestions="props.promptSuggestions"
          :world-memories="props.worldMemories"
          :can-send-input="canSendInput"
          :debug-mode="!!props.sheet?.debug_mode"
          @open-quests="emit('openQuests')"
          @open-map="emit('openMap')"
          @open-sheet="emit('openSheet')"
          @open-chronicles="emit('openChronicles')"
          @open-walkthrough="emit('openWalkthrough')"
          @open-memories="emit('openMemories')"
          @open-debug="emit('openDebug')"
          @select-suggestion="handleSuggestionSelect"
          @shuffle-suggestions="handleSuggestionShuffle"
        />
      </div>

      <ImmersiveInputBar
        ref="inputBarRef"
        :can-send-input="canSendInput"
        :is-evaluating="isEvaluating"
        :status-text="props.statusText"
        :agent-active="props.sheet?.agent_active"
        :debug-mode="!!props.sheet?.debug_mode"
        :turn-error="props.turnError"
        @send="handleSend"
        @retry-turn="emit('retryTurn')"
        @cancel-turn-error="emit('cancelTurnError')"
      />
    </footer>

    <!-- 5. CINEMATIC SCENE TRANSITION CURTAIN (covers the whole game view, header and footer included) -->
    <SceneTransitionOverlay
      :active="Boolean(props.isSceneTransitioning || props.exitTraversalBusy)"
      :target-scene-name="props.sceneTransitionTarget?.targetSceneName"
      :exit-label="props.sceneTransitionTarget?.label"
      :status-text="props.statusText"
      :background-image-url="transitionSceneImageUrl"
    />

    <!-- 6. CINEMATIC SEQUENCE TITLE OVERLAY (full window, above the travel curtain) -->
    <CinematicSequenceOverlay
      :active-sequence="props.activeSequence"
      :adventure-title="props.adventureTitle"
    />

    <SceneImageViewer
      v-if="showSceneImage && activeSceneImageUrl"
      :image-url="activeSceneImageUrl"
      :scene-name="props.currentSceneName || props.sheet?.current_scene"
      @close="showSceneImage = false"
    />
  </div>
</template>

<style scoped>
.tw-action-reveal {
  display: grid;
  grid-template-rows: 0fr;
  opacity: 0;
  transition: grid-template-rows 0.2s ease, opacity 0.2s ease;
}

.tw-action-reveal > * {
  min-height: 0;
  overflow: hidden;
}

.tw-footer:hover .tw-action-reveal,
.tw-action-reveal:focus-within,
.tw-action-reveal.is-pinned {
  grid-template-rows: 1fr;
  opacity: 1;
}

/* Revealed: let upward popovers (ideas) overflow the bar. */
.tw-footer:hover .tw-action-reveal > *,
.tw-action-reveal:focus-within > *,
.tw-action-reveal.is-pinned > * {
  overflow: visible;
}

/* Touch devices cannot hover: keep the buttons visible. */
@media (hover: none) {
  .tw-action-reveal {
    grid-template-rows: 1fr;
    opacity: 1;
  }

  .tw-action-reveal > * {
    overflow: visible;
  }
}
</style>
