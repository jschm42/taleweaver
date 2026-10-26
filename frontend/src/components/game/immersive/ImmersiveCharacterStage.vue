<script setup lang="ts">
/**
 * ImmersiveCharacterStage — Left-side 2:3 vertical character cards
 *
 * Displays portraits of the protagonist and scene NPCs with active speaker auras,
 * health status, defeat tags, and quick click/hover interactions. Characters joining the scene
 * get a skin-specific entrance (see src/skins/entrances.css).
 */
import { ref, watch, nextTick, computed } from 'vue'
import { getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  npcs: any[]
  activeSpeakers: Set<string>
  activeTurnIndex?: number
}>()

const emit = defineEmits<{
  npcClick: [npc: any]
  npcHover: [entity: any, event: MouseEvent]
  npcLeave: []
  npcContextmenu: [npc: any, event: MouseEvent]
}>()

const stageContainerRef = ref<HTMLElement | null>(null)
const brokenImages = ref<Record<string, boolean>>({})

function scrollToTop() {
  if (!stageContainerRef.value) return
  stageContainerRef.value.scrollTo({
    top: 0,
    behavior: 'smooth'
  })
}

const activeSpeakersSignature = computed(() => {
  if (!props.activeSpeakers || props.activeSpeakers.size === 0) return ''
  return Array.from(props.activeSpeakers).sort().join(',')
})

const hasSpeakingNpc = computed(() => {
  if (!props.activeSpeakers || props.activeSpeakers.size === 0) return false
  return (props.npcs || []).some((npc) => isNpcSpeaking(npc))
})

watch(
  [() => props.activeTurnIndex, activeSpeakersSignature],
  () => {
    if (hasSpeakingNpc.value) {
      nextTick(() => {
        scrollToTop()
      })
    }
  }
)

function handleImageError(path?: string | null) {
  if (!path) return
  brokenImages.value[path] = true
}

function onImageLoadError(e: Event, path?: string | null) {
  if (!path) return
  const target = e.target as HTMLImageElement
  if (target && target.src && target.src.includes('_thumb')) {
    target.src = getOriginalImageUrl(path)
  } else {
    handleImageError(path)
  }
}

function showImage(path?: string | null) {
  return !!path && !brokenImages.value[path]
}

// --- Entrances: characters that join the scene after the stage was first filled ---
const ARRIVAL_HIGHLIGHT_MS = 2600
const recentArrivals = ref<Set<string>>(new Set())
/** Entrance transitions start only after the first cast has rendered (no animation on load). */
const stageReady = ref(false)

watch(
  () => (props.npcs || []).map((npc) => String(npc.id)),
  (ids, previousIds) => {
    if (!stageReady.value) {
      if (ids.length) {
        nextTick(() => {
          stageReady.value = true
        })
      }
      return
    }
    const known = new Set(previousIds ?? [])
    const arrivals = ids.filter((id) => !known.has(id))
    if (!arrivals.length) {
      return
    }
    recentArrivals.value = new Set([...recentArrivals.value, ...arrivals])
    window.setTimeout(() => {
      const remaining = new Set(recentArrivals.value)
      arrivals.forEach((id) => remaining.delete(id))
      recentArrivals.value = remaining
    }, ARRIVAL_HIGHLIGHT_MS)
  }
)

function hasJustArrived(npc: any): boolean {
  return recentArrivals.value.has(String(npc.id))
}

function isNpcSpeaking(npc: any): boolean {
  if (!npc || !props.activeSpeakers) return false
  const nameMatch = npc.name && props.activeSpeakers.has(npc.name.toLowerCase())
  const idMatch = npc.id && props.activeSpeakers.has(String(npc.id).toLowerCase())
  return Boolean(nameMatch || idMatch)
}
</script>

<template>
  <aside
    ref="stageContainerRef"
    class="flex flex-col gap-2 shrink-0 overflow-y-auto w-16 sm:w-[5.6rem] md:w-[7.2rem] lg:w-[8.8rem] custom-scrollbar pr-1 py-1 max-h-full"
  >
    <TransitionGroup :name="stageReady ? 'tw-npc' : 'tw-npc-initial'" tag="div" class="flex flex-col gap-2 w-full">
      <div
        v-for="npc in props.npcs"
        :key="npc.id"
        class="relative group flex flex-col items-center bg-slate-950 rounded-xl border-2 transition-all duration-300 shrink-0 w-full aspect-[2/3] overflow-hidden cursor-pointer shadow-[0_6px_20px_rgba(0,0,0,0.7)] active:scale-98"
        :class="[
          { 'tw-npc-arrived': hasJustArrived(npc) },
          isNpcSpeaking(npc)
            ? 'border-amber-400 shadow-[0_0_25px_rgba(251,191,36,0.6)] ring-2 ring-amber-400/60'
            : 'border-slate-700/70 hover:border-cyan-400/80'
        ]"
        @click="emit('npcClick', npc)"
        @mouseenter="emit('npcHover', npc, $event)"
        @mousemove="emit('npcHover', npc, $event)"
        @mouseleave="emit('npcLeave')"
        @contextmenu.prevent="emit('npcContextmenu', npc, $event)"
      >
        <!-- Full 2:3 Character Portrait -->
        <img
          v-if="npc.image_url && showImage(npc.image_url)"
          :src="getImageUrl(npc.image_url, { thumbnail: true })"
          :alt="npc.name"
          class="w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-105"
          :class="{ 'grayscale opacity-50': npc.is_defeated || npc.hp === 0 }"
          @error="onImageLoadError($event, npc.image_url)"
        />
        <div v-else class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-b from-slate-900 to-slate-950 text-slate-600">
          <i class="ra ra-helmet text-4xl mb-1 text-cyan-400"></i>
        </div>

        <!-- Entrance: one-off light sweep and a short "Enters" tag -->
        <div v-if="hasJustArrived(npc)" class="tw-npc-sweep" aria-hidden="true"></div>
        <div v-if="hasJustArrived(npc)" class="tw-npc-arrival-tag">Enters</div>

        <!-- Active Speaker Badge -->
        <div v-if="isNpcSpeaking(npc)" class="absolute top-2 right-2 z-20 px-1.5 py-0.5 rounded-full bg-amber-500 text-black text-[8px] font-black uppercase tracking-wider shadow-md animate-bounce">
          Speaking
        </div>

        <!-- Defeated Ribbon -->
        <div v-if="npc.is_defeated || npc.hp === 0" class="absolute -right-6 top-3 bg-red-600 text-white text-[8px] font-black uppercase tracking-[0.12em] py-0.5 w-24 text-center rotate-45 shadow-lg z-20">
          Defeated
        </div>

        <!-- Name & Role Overlay with Gradient & Strong Shadow -->
        <div class="absolute inset-x-0 bottom-0 pt-8 pb-2 px-2 bg-gradient-to-t from-black/95 via-black/60 to-transparent flex flex-col items-center text-center pointer-events-none z-10">
          <h4 class="text-[11px] sm:text-xs font-black text-white group-hover:text-amber-300 transition-colors uppercase tracking-wider drop-shadow-[0_2px_3px_rgba(0,0,0,1)] truncate w-full">
            {{ npc.name }}
          </h4>
          <span v-if="npc.role" class="text-[9px] font-bold text-slate-300/90 uppercase tracking-widest drop-shadow-[0_1px_2px_rgba(0,0,0,1)] truncate w-full mt-0.5">
            {{ npc.role }}
          </span>
        </div>
      </div>
    </TransitionGroup>
  </aside>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.1); }

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
