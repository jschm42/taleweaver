<script setup lang="ts">
/**
 * ImmersiveStoryFeed — Comic story pages and page history
 *
 * A page covers one scene + sequence (chapter) and shows all of its exchanges in order
 * (see comicPages.ts). The page only changes when the scene or the sequence changes.
 */
import { ref, watch, nextTick } from 'vue'
import type { ComicTurn } from '@/composables/useComicTurns'
import LicenseInfoBlock from '@/components/game/LicenseInfoBlock.vue'
import ImmersiveStoryExchange from '@/components/game/immersive/ImmersiveStoryExchange.vue'
import { Sparkles, ChevronLeft, ChevronRight, Compass } from 'lucide-vue-next'

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

// New page: start reading at the top.
watch(() => props.activeTurnIndex, () => {
  nextTick(() => {
    if (storyContainerRef.value) {
      storyContainerRef.value.scrollTop = 0
    }
  })
})

// New exchange on the page being followed: scroll to its beginning.
watch(
  () => props.activeTurn?.exchanges.length ?? 0,
  (count, previousCount) => {
    if (props.viewingTurnIndex !== null || count <= previousCount) return
    nextTick(() => {
      const exchanges = storyContainerRef.value?.querySelectorAll('[data-story-exchange]')
      const latest = exchanges?.[exchanges.length - 1] as HTMLElement | undefined
      latest?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    })
  }
)

function isLatestExchange(exIdx: number): boolean {
  const isLatestPage = props.activeTurnIndex >= props.gameTurns.length - 1
  return isLatestPage && exIdx === (props.activeTurn?.exchanges.length ?? 0) - 1
}
</script>

<template>
  <div class="flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
    <!-- COMIC STORY CONTAINER (Page Display) -->
    <div
      ref="storyContainerRef"
      class="comic-story-container flex-1 overflow-y-auto custom-scrollbar p-2 sm:p-4 flex flex-col gap-4 min-h-0 relative"
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
        <LicenseInfoBlock v-if="props.activeTurn.licenseMessage" :msg="props.activeTurn.licenseMessage" class="shrink-0" />

        <!-- EXCHANGES OF THIS SCENE -->
        <ImmersiveStoryExchange
          v-for="(exchange, exIdx) in props.activeTurn.exchanges"
          :key="exchange.userMessage?.id || exchange.assistantMessage?.id || exIdx"
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
    </div>

    <!-- COMIC PAGE NAVIGATION & PAGING CONTROLS -->
    <div v-if="props.gameTurns.length > 1" class="flex items-center justify-between px-3 py-1.5 bg-slate-950/80 border-t border-slate-800/80 shrink-0 text-xs font-bold text-slate-400">
      <div class="flex items-center gap-1">
        <button
          type="button"
          :disabled="props.activeTurnIndex <= 0"
          @click="emit('goToTurn', props.activeTurnIndex - 1)"
          class="p-1 rounded bg-slate-900 border border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed hover:text-white cursor-pointer"
          title="Previous Turn"
        >
          <ChevronLeft class="w-3.5 h-3.5" />
        </button>
        <span class="px-2 font-mono">Turn {{ props.activeTurnIndex + 1 }} / {{ props.gameTurns.length }}</span>
        <button
          type="button"
          :disabled="props.activeTurnIndex >= props.gameTurns.length - 1"
          @click="emit('goToTurn', props.activeTurnIndex + 1)"
          class="p-1 rounded bg-slate-900 border border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed hover:text-white cursor-pointer"
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
  </div>
</template>

<style scoped>
.comic-story-container > * {
  flex-shrink: 0;
}

.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.2); }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.3); }
</style>
