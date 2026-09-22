<script setup lang="ts">
/**
 * ImmersiveSceneHotspots — Interactive scene hotspots
 *
 * Displays compact Wayfinder (Exits) and Discoveries (Room Stash) popover buttons
 * alongside tactical switches, eliminating badge clutter from the story view.
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getItemIcon, getTypeColor, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import { Compass, DoorOpen, Lock, Hand, Sparkles, Eye, X, ArrowRight, Terminal } from 'lucide-vue-next'

const props = defineProps<{
  sceneExits: any[]
  sceneSwitches: any[]
  items: any[]
  systemMessages?: any[]
  isEvaluating?: boolean
  showMobileInteract?: boolean
  currentSceneName?: string | null
}>()

const emit = defineEmits<{
  traverseExit: [exit: any]
  switchFlip: [entity: any]
  itemClick: [item: any]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  itemContextmenu: [item: any, event: MouseEvent]
  takeDirect: [item: any]
}>()

const showExitsPopover = ref(false)
const showDiscoveriesPopover = ref(false)
const showSystemPopover = ref(false)

const exitsContainerRef = ref<HTMLElement | null>(null)
const discoveriesContainerRef = ref<HTMLElement | null>(null)
const systemContainerRef = ref<HTMLElement | null>(null)

const isTakingAll = ref(false)
const brokenImages = ref<Record<string, boolean>>({})

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

function formatSceneTitle(name?: string | null): string {
  if (!name) return ''
  const trimmed = String(name).trim()
  if (trimmed.includes('_') || trimmed.includes('-') || /^[A-Z0-9\s_-]+$/.test(trimmed)) {
    return trimmed
      .replace(/[_-]+/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, c => c.toUpperCase())
  }
  return trimmed
}

function getItemTypeBorderClass(type?: string) {
  switch (type?.toUpperCase()) {
    case 'WEAPON':
      return 'border-rose-500/70 hover:border-rose-400 shadow-[0_4px_20px_rgba(244,63,94,0.18)]'
    case 'CONSUMABLE':
      return 'border-emerald-500/70 hover:border-emerald-400 shadow-[0_4px_20px_rgba(16,185,129,0.18)]'
    case 'KEY':
    case 'KEYS':
      return 'border-amber-400/80 hover:border-amber-300 shadow-[0_4px_20px_rgba(251,191,36,0.18)]'
    case 'READABLE':
      return 'border-indigo-400/80 hover:border-indigo-300 shadow-[0_4px_20px_rgba(129,140,248,0.18)]'
    case 'TOOL':
      return 'border-sky-500/70 hover:border-sky-400 shadow-[0_4px_20px_rgba(14,165,233,0.18)]'
    case 'WEARABLE':
      return 'border-blue-500/70 hover:border-blue-400 shadow-[0_4px_20px_rgba(59,130,246,0.18)]'
    case 'COMBINABLE':
      return 'border-fuchsia-500/70 hover:border-fuchsia-400 shadow-[0_4px_20px_rgba(217,70,239,0.18)]'
    case 'CONSTRUCTABLE':
      return 'border-orange-500/70 hover:border-orange-400 shadow-[0_4px_20px_rgba(249,115,22,0.18)]'
    case 'SWITCH':
      return 'border-lime-500/70 hover:border-lime-400 shadow-[0_4px_20px_rgba(132,204,22,0.18)]'
    default:
      return 'border-slate-700/80 hover:border-cyan-400/60 shadow-[0_4px_20px_rgba(0,0,0,0.3)]'
  }
}

const hasLockedExits = computed(() => {
  return Array.isArray(props.sceneExits) && props.sceneExits.some((e: any) => e.is_locked)
})

const portableItems = computed(() => {
  return Array.isArray(props.items) ? props.items.filter((item: any) => item.is_portable !== false) : []
})

const canTakeAll = computed(() => {
  return portableItems.value.length > 0 && !props.isEvaluating && !isTakingAll.value
})

function toggleExitsPopover() {
  showExitsPopover.value = !showExitsPopover.value
  if (showExitsPopover.value) {
    showDiscoveriesPopover.value = false
    showSystemPopover.value = false
  }
}

function toggleDiscoveriesPopover() {
  showDiscoveriesPopover.value = !showDiscoveriesPopover.value
  if (showDiscoveriesPopover.value) {
    showExitsPopover.value = false
    showSystemPopover.value = false
  }
}

function toggleSystemPopover() {
  showSystemPopover.value = !showSystemPopover.value
  if (showSystemPopover.value) {
    showExitsPopover.value = false
    showDiscoveriesPopover.value = false
  }
}

function closeAllPopovers() {
  showExitsPopover.value = false
  showDiscoveriesPopover.value = false
  showSystemPopover.value = false
}

function handleTraverse(exit: any) {
  emit('traverseExit', exit)
  showExitsPopover.value = false
}

async function handleTakeAll() {
  if (!canTakeAll.value) return
  isTakingAll.value = true
  try {
    for (const item of portableItems.value) {
      emit('takeDirect', item)
      await new Promise(resolve => setTimeout(resolve, 250))
    }
  } finally {
    isTakingAll.value = false
  }
}

function handleDocumentClick(e: MouseEvent) {
  const target = e.target as HTMLElement | null
  if (!target) return
  if (showExitsPopover.value && exitsContainerRef.value && !exitsContainerRef.value.contains(target)) {
    showExitsPopover.value = false
  }
  if (showDiscoveriesPopover.value && discoveriesContainerRef.value && !discoveriesContainerRef.value.contains(target)) {
    showDiscoveriesPopover.value = false
  }
  if (showSystemPopover.value && systemContainerRef.value && !systemContainerRef.value.contains(target)) {
    showSystemPopover.value = false
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    closeAllPopovers()
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  document.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
  document.removeEventListener('keydown', handleKeydown)
})

// Exit Tooltip State
const hoveredExit = ref<any | null>(null)
const hoveredExitPos = ref({ x: 0, y: 0 })

function handleExitMouseEnter(exit: any, event: MouseEvent) {
  hoveredExit.value = exit
  hoveredExitPos.value = { x: event.clientX, y: event.clientY }
}

function handleExitMouseLeave() {
  hoveredExit.value = null
}

function handleExitMouseMove(event: MouseEvent) {
  if (hoveredExit.value) {
    hoveredExitPos.value = { x: event.clientX, y: event.clientY }
  }
}
</script>

<template>
  <div class="relative shrink-0 z-30">
    <!-- Floating Interactive Scene Hotspots Toolbar -->
    <div
      class="shrink-0"
      :class="[
        props.isEvaluating ? 'opacity-50 pointer-events-none' : '',
        props.showMobileInteract
          ? 'absolute right-2 top-2 bg-slate-900/95 p-3 rounded-2xl border border-slate-700 shadow-2xl max-w-[85vw] flex flex-col gap-2 z-50'
          : 'hidden md:flex flex-wrap items-center gap-2 mb-3'
      ]"
    >
      <!-- 1. EXITS (WAYFINDER) BUTTON & POPOVER -->
      <div
        v-if="props.sceneExits && props.sceneExits.length > 0"
        ref="exitsContainerRef"
        class="relative"
      >
        <button
          type="button"
          class="group flex items-center gap-2 px-3.5 py-1.5 rounded-xl border backdrop-blur-md transition-all shadow-md cursor-pointer active:scale-95"
          :class="[
            showExitsPopover
              ? 'bg-amber-500/20 border-amber-400 text-amber-200 ring-2 ring-amber-400/30'
              : 'bg-slate-900/85 hover:bg-slate-800 border-slate-700/80 hover:border-amber-400/60 text-slate-200 hover:text-white'
          ]"
          @click.stop="toggleExitsPopover"
          title="View Exits and Passages"
        >
          <Compass
            class="w-4 h-4 text-amber-400 group-hover:rotate-45 transition-transform duration-300"
          />
          <span class="text-xs font-bold uppercase tracking-wider">Passages</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] font-black bg-amber-400/20 text-amber-300 border border-amber-400/30">
            {{ props.sceneExits.length }}
          </span>
          <span
            v-if="hasLockedExits"
            class="flex items-center text-red-400 text-[10px]"
            title="Contains locked passage"
          >
            <Lock class="w-3 h-3 text-red-400" />
          </span>
        </button>

        <!-- WAYFINDER POPOVER -->
        <Transition name="popover">
          <div
            v-if="showExitsPopover"
            class="absolute top-full left-0 mt-2 z-50 w-[calc(100vw-2rem)] sm:w-80 md:w-96 max-w-sm bg-slate-950/95 border border-slate-700/80 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.7)] backdrop-blur-2xl p-3 flex flex-col gap-2"
          >
            <!-- Header -->
            <div class="flex items-center justify-between pb-2 border-b border-slate-800">
              <div class="flex items-center gap-2">
                <Compass class="w-4 h-4 text-amber-400" />
                <span class="text-xs font-black uppercase text-slate-200 tracking-wider">Passages & Exits</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-[10px] text-slate-400 font-bold">
                  {{ props.sceneExits.length }} {{ props.sceneExits.length === 1 ? 'Route' : 'Routes' }}
                </span>
                <button
                  type="button"
                  class="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
                  @click.stop="showExitsPopover = false"
                  title="Close"
                >
                  <X class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <!-- Exit list -->
            <div class="space-y-1.5 max-h-64 overflow-y-auto pr-1">
              <div
                v-for="exit in props.sceneExits"
                :key="exit.id || exit.label"
                class="group flex items-center justify-between p-2 rounded-xl bg-slate-900/70 hover:bg-slate-800/90 border border-slate-800/90 hover:border-amber-400/50 cursor-pointer transition-all active:scale-[0.98]"
                @click="handleTraverse(exit)"
                @mouseenter="e => handleExitMouseEnter(exit, e)"
                @mouseleave="handleExitMouseLeave"
                @mousemove="handleExitMouseMove"
              >
                <div class="flex items-center gap-2.5 min-w-0">
                  <div
                    class="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border"
                    :class="exit.is_locked ? 'bg-amber-950/40 border-amber-500/30 text-amber-400' : 'bg-emerald-950/40 border-emerald-500/30 text-emerald-400'"
                  >
                    <Lock v-if="exit.is_locked" class="w-3.5 h-3.5" />
                    <DoorOpen v-else class="w-3.5 h-3.5" />
                  </div>
                  <div class="min-w-0">
                    <p class="text-xs font-bold text-white uppercase tracking-tight truncate group-hover:text-amber-300 transition-colors">
                      {{ exit.label || 'Exit' }}
                    </p>
                    <p v-if="exit.target_scene_name || exit.target_scene_id" class="text-[10px] text-slate-400 flex items-center gap-1 truncate">
                      <span>{{ props.currentSceneName || 'Current' }}</span>
                      <ArrowRight class="w-2.5 h-2.5 text-slate-600 shrink-0" />
                      <span class="text-slate-300 font-medium truncate">{{ exit.target_scene_name || formatSceneTitle(exit.target_scene_id) }}</span>
                    </p>
                  </div>
                </div>

                <span
                  class="shrink-0 text-[9px] font-black uppercase px-2 py-0.5 rounded-full"
                  :class="exit.is_locked ? 'bg-red-500/20 text-red-300 border border-red-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'"
                >
                  {{ exit.is_locked ? 'Locked' : 'Open' }}
                </span>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- 2. SCENE ITEMS / DISCOVERIES (CONCEPT B) BUTTON & POPOVER -->
      <div
        v-if="props.items && props.items.length > 0"
        ref="discoveriesContainerRef"
        class="relative"
      >
        <button
          type="button"
          class="group flex items-center gap-2 px-3.5 py-1.5 rounded-xl border backdrop-blur-md transition-all shadow-md cursor-pointer active:scale-95"
          :class="[
            showDiscoveriesPopover
              ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 ring-2 ring-cyan-400/30'
              : 'bg-slate-900/85 hover:bg-slate-800 border-slate-700/80 hover:border-cyan-400/60 text-slate-200 hover:text-white'
          ]"
          @click.stop="toggleDiscoveriesPopover"
          title="View Discovered Objects in Scene"
        >
          <Sparkles
            class="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform"
          />
          <span class="text-xs font-bold uppercase tracking-wider">Discoveries</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] font-black bg-cyan-400/20 text-cyan-300 border border-cyan-400/30">
            {{ props.items.length }}
          </span>
        </button>

        <!-- DISCOVERIES POPOVER -->
        <Transition name="popover">
          <div
            v-if="showDiscoveriesPopover"
            class="absolute top-full left-0 mt-2 z-50 w-[calc(100vw-2rem)] sm:w-[28rem] md:w-[32rem] max-w-lg bg-slate-950/95 border border-slate-700/80 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.7)] backdrop-blur-2xl p-3 flex flex-col gap-2"
          >
            <!-- Header -->
            <div class="flex items-center justify-between pb-2 border-b border-slate-800">
              <div class="flex items-center gap-2">
                <Sparkles class="w-4 h-4 text-cyan-400" />
                <span class="text-xs font-black uppercase text-slate-200 tracking-wider">Room Discoveries</span>
                <span class="text-[10px] font-bold text-slate-400">({{ props.items.length }})</span>
              </div>

              <div class="flex items-center gap-2">
                <!-- Take All Button -->
                <button
                  v-if="canTakeAll"
                  type="button"
                  class="px-2 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-[11px] font-bold flex items-center gap-1 transition-all active:scale-95 cursor-pointer disabled:opacity-50"
                  :disabled="isTakingAll || props.isEvaluating"
                  @click.stop="handleTakeAll"
                  title="Collect all portable items into inventory"
                >
                  <Hand class="w-3 h-3 text-emerald-400" />
                  <span>Take All ({{ portableItems.length }})</span>
                </button>

                <button
                  type="button"
                  class="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
                  @click.stop="showDiscoveriesPopover = false"
                  title="Close"
                >
                  <X class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <!-- Items 2-Column Tile Grid -->
            <div class="grid grid-cols-2 gap-2.5 max-h-84 overflow-y-auto pr-1 custom-scrollbar">
              <div
                v-for="item in props.items"
                :key="item.id"
                class="group relative flex flex-col items-center justify-between p-3 rounded-2xl bg-slate-900/85 hover:bg-slate-800/95 border-2 transition-all shadow-md cursor-pointer active:scale-[0.98]"
                :class="getItemTypeBorderClass(item.item_type)"
                @click="emit('itemClick', item)"
                @mouseenter="emit('itemHover', item, $event)"
                @mouseleave="emit('itemLeave')"
                @contextmenu.prevent="emit('itemContextmenu', item, $event)"
              >
                <!-- Floating Take Button (top-right) -->
                <button
                  v-if="item.is_portable !== false"
                  type="button"
                  class="absolute top-2 right-2 z-10 p-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 hover:scale-110 transition-all shadow-md cursor-pointer"
                  title="Take Item"
                  @click.stop="emit('takeDirect', item)"
                >
                  <Hand class="w-3.5 h-3.5 text-emerald-400" />
                </button>

                <!-- Hero Icon / Artwork (Large) -->
                <div class="w-16 h-16 sm:w-20 sm:h-20 rounded-xl overflow-hidden bg-slate-950/90 border border-white/10 flex items-center justify-center shrink-0 shadow-inner group-hover:scale-105 transition-transform my-1">
                  <img
                    v-if="item.image_url && showImage(item.image_url)"
                    :src="getImageUrl(item.image_url, { thumbnail: true })"
                    :alt="item.name"
                    class="w-full h-full object-cover"
                    @error="onImageLoadError($event, item.image_url)"
                  />
                  <i v-else :class="['ra text-3xl sm:text-4xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                </div>

                <!-- Item Name (Centered, clean) -->
                <div class="mt-1.5 w-full text-center">
                  <p class="text-xs font-bold text-slate-200 group-hover:text-white uppercase tracking-tight line-clamp-2 leading-snug transition-colors px-1">
                    {{ item.name }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- 3. SYSTEM MESSAGES BUTTON & POPOVER -->
      <div
        v-if="props.systemMessages && props.systemMessages.length > 0"
        ref="systemContainerRef"
        class="relative"
      >
        <button
          type="button"
          class="group flex items-center gap-2 px-3.5 py-1.5 rounded-xl border backdrop-blur-md transition-all shadow-md cursor-pointer active:scale-95"
          :class="[
            showSystemPopover
              ? 'bg-emerald-500/20 border-emerald-400 text-emerald-200 ring-2 ring-emerald-400/30'
              : 'bg-slate-900/85 hover:bg-slate-800 border-slate-700/80 hover:border-emerald-400/60 text-slate-200 hover:text-white'
          ]"
          @click.stop="toggleSystemPopover"
          title="View System Messages"
        >
          <Terminal
            class="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform"
          />
          <span class="text-xs font-bold uppercase tracking-wider">System</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] font-black bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">
            {{ props.systemMessages.length }}
          </span>
        </button>

        <!-- SYSTEM POPOVER -->
        <Transition name="popover">
          <div
            v-if="showSystemPopover"
            class="absolute top-full left-0 mt-2 z-50 w-[calc(100vw-2rem)] sm:w-96 md:w-[32rem] max-w-lg bg-slate-950/95 border border-slate-700/80 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.8)] backdrop-blur-2xl p-3 flex flex-col gap-2"
          >
            <!-- Header -->
            <div class="flex items-center justify-between pb-2 border-b border-slate-800">
              <div class="flex items-center gap-2">
                <Terminal class="w-4 h-4 text-emerald-400" />
                <span class="text-xs font-black uppercase text-slate-200 tracking-wider">System Messages</span>
                <span class="text-[10px] font-bold text-slate-400">({{ props.systemMessages.length }})</span>
              </div>

              <button
                type="button"
                class="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
                @click.stop="showSystemPopover = false"
                title="Close"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>

            <!-- Messages List -->
            <div class="space-y-2 max-h-72 overflow-y-auto pr-1 custom-scrollbar">
              <div
                v-for="(sysMsg, sIdx) in props.systemMessages"
                :key="sIdx"
                class="p-2.5 rounded-xl bg-slate-900/80 border border-emerald-500/20 border-l-4 border-l-emerald-500 text-slate-200 text-xs sm:text-sm leading-relaxed"
              >
                <div class="flex items-center gap-2 mb-1">
                  <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    System
                  </span>
                  <span v-if="sysMsg.timestamp" class="text-[10px] text-slate-500">
                    {{ sysMsg.timestamp }}
                  </span>
                </div>
                <p class="italic text-emerald-100/90 whitespace-pre-wrap">
                  {{ sysMsg.content }}
                </p>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- 4. SWITCHES (LEVERS) -->
      <div
        v-for="sw in props.sceneSwitches"
        :key="sw.id"
        class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/85 hover:bg-slate-800 border border-lime-500/40 text-slate-200 hover:text-lime-300 backdrop-blur-md transition-all shadow-md cursor-pointer active:scale-95"
        @click="emit('switchFlip', sw)"
        :title="`Toggle ${sw.name}`"
      >
        <i class="ra ra-lever text-lime-400 text-sm"></i>
        <span class="text-xs font-bold uppercase tracking-wider truncate max-w-[8rem]">{{ sw.name }}</span>
        <span class="px-1.5 py-0.2 bg-lime-500/20 text-lime-300 text-[9px] font-black rounded-full uppercase">
          {{ String(sw.switch_state || sw.metadata_json?.switch?.initial_state || '—').toUpperCase() }}
        </span>
      </div>
    </div>

    <!-- EXIT HOVER TOOLTIP -->
    <Teleport to="body">
      <Transition name="tooltip">
        <div 
          v-if="hoveredExit" 
          class="fixed z-[110] pointer-events-none transition-all duration-75"
          :style="{ left: (hoveredExitPos.x + 20) + 'px', top: (hoveredExitPos.y - 40) + 'px' }"
        >
          <div class="w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl overflow-hidden flex flex-col p-4 animate-tooltip-in">
            <div class="flex items-center justify-between mb-2 pb-2 border-b border-slate-800">
              <span class="text-xs font-black uppercase text-slate-400 tracking-wider">Exit Connection</span>
              <span 
                class="text-[9px] px-2 py-0.5 rounded-full font-black uppercase tracking-tight"
                :class="hoveredExit.is_locked ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'"
              >
                {{ hoveredExit.is_locked ? 'Locked' : 'Unlocked' }}
              </span>
            </div>
            <p class="text-xs font-bold text-white mb-1 uppercase tracking-tight">{{ hoveredExit.label }}</p>
            <p class="text-[10px] font-bold text-slate-500 flex items-center gap-1.5" v-if="hoveredExit.target_scene_name || hoveredExit.target_scene_id">
              {{ props.currentSceneName || 'Current Location' }} 
              <i class="ra ra-plain-arrow text-slate-600"></i>
              <span class="text-slate-300">{{ hoveredExit.target_scene_name || formatSceneTitle(hoveredExit.target_scene_id) }}</span>
            </p>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}

/* Popover Transitions */
.popover-enter-active, .popover-leave-active {
  transition: opacity 0.18s cubic-bezier(0.16, 1, 0.3, 1), transform 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}
.popover-enter-from, .popover-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.97);
}

/* Tooltip Animations */
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.96) translateY(4px); }

.animate-tooltip-in {
  animation: toolTipIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(6px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
