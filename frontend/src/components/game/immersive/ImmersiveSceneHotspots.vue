<script setup lang="ts">
/**
 * ImmersiveSceneHotspots — Interactive scene hotspots
 *
 * Displays badges for scene exits, levers/switches, and discovered items,
 * with exit hover tooltip teleportation and mobile interactive drawer support.
 */
import { ref } from 'vue'
import { getItemIcon, getTypeColor, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import { DoorOpen, Lock, Hand } from 'lucide-vue-next'

const props = defineProps<{
  sceneExits: any[]
  sceneSwitches: any[]
  items: any[]
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
  <div>
    <!-- Floating Interactive Scene Hotspots (Items, Switches, Exits) -->
    <div
      class="shrink-0 z-50 md:z-10"
      :class="[
        props.isEvaluating ? 'opacity-50 pointer-events-none' : '',
        props.showMobileInteract
          ? 'absolute right-2 top-2 bg-slate-900/95 p-3 rounded-2xl border border-slate-700 shadow-2xl max-w-[70vw] max-h-[60vh] overflow-y-auto flex flex-col gap-2'
          : 'hidden md:flex flex-wrap items-center gap-2 mb-3'
      ]"
    >
      <!-- Exits / Portals -->
      <div
        v-for="exit in props.sceneExits"
        :key="exit.id || exit.label"
        class="group flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/85 hover:bg-slate-800 border border-slate-700/80 hover:border-amber-400/60 text-slate-200 hover:text-white backdrop-blur-md transition-all shadow-lg cursor-pointer active:scale-95"
        @click="emit('traverseExit', exit)"
        @mouseenter="e => handleExitMouseEnter(exit, e)"
        @mouseleave="handleExitMouseLeave"
        @mousemove="handleExitMouseMove"
      >
        <Lock
          v-if="exit.is_locked"
          class="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform"
        />
        <DoorOpen
          v-else
          class="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform"
        />
        <span class="text-xs font-bold uppercase tracking-wider truncate max-w-[8rem]">{{ exit.label || 'Exit' }}</span>
        <span v-if="exit.is_locked" class="px-1.5 py-0.2 bg-red-500/20 text-red-300 border border-red-500/30 text-[9px] font-black rounded-full uppercase">
          Locked
        </span>
      </div>

      <!-- Switches -->
      <div
        v-for="sw in props.sceneSwitches"
        :key="sw.id"
        class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/85 hover:bg-slate-800 border border-lime-500/40 text-slate-200 hover:text-lime-300 backdrop-blur-md transition-all shadow-lg cursor-pointer active:scale-95"
        @click="emit('switchFlip', sw)"
      >
        <i class="ra ra-lever text-lime-400 text-sm"></i>
        <span class="text-xs font-bold uppercase tracking-wider truncate max-w-[8rem]">{{ sw.name }}</span>
        <span class="px-1.5 py-0.2 bg-lime-500/20 text-lime-300 text-[9px] font-black rounded-full uppercase">
          {{ String(sw.switch_state || sw.metadata_json?.switch?.initial_state || '—').toUpperCase() }}
        </span>
      </div>

      <!-- Scene Items / Discoveries with Rich Image / RPG Icon -->
      <div
        v-for="item in props.items"
        :key="item.id"
        class="group flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/85 hover:bg-slate-800 border border-cyan-500/40 hover:border-cyan-400 text-slate-200 hover:text-cyan-300 backdrop-blur-md transition-all shadow-lg cursor-pointer active:scale-95"
        @click="emit('itemClick', item)"
        @mouseenter="emit('itemHover', item, $event)"
        @mouseleave="emit('itemLeave')"
        @contextmenu.prevent="emit('itemContextmenu', item, $event)"
      >
        <div class="w-6 h-6 rounded-md overflow-hidden bg-slate-950 border border-slate-700/80 flex items-center justify-center shrink-0">
          <img
            v-if="item.image_url && showImage(item.image_url)"
            :src="getImageUrl(item.image_url, { thumbnail: true })"
            :alt="item.name"
            class="w-full h-full object-cover"
            @error="onImageLoadError($event, item.image_url)"
          />
          <i v-else :class="['ra text-sm', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
        </div>

        <span class="text-xs font-bold uppercase tracking-wider truncate max-w-[9rem]">{{ item.name }}</span>

        <span
          v-if="String(item.item_type || '').toUpperCase() === 'READABLE'"
          class="px-1 py-0.2 rounded text-[8px] font-black uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
        >
          Note
        </span>

        <button
          v-if="item.is_portable !== false"
          type="button"
          class="ml-1 text-slate-400 hover:text-emerald-400 p-1 rounded-md bg-slate-800/80 hover:bg-slate-700 transition-colors cursor-pointer"
          title="Take Item"
          @click.stop="emit('takeDirect', item)"
        >
          <Hand class="w-3 h-3 text-emerald-400" />
        </button>
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
            <p class="text-[10px] font-bold text-slate-500 flex items-center gap-1.5" v-if="hoveredExit.target_scene_id">
              {{ props.currentSceneName || 'Current Location' }} 
              <i class="ra ra-plain-arrow text-slate-600"></i>
              <span class="text-slate-300">{{ hoveredExit.target_scene_id }}</span>
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
