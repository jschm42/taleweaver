<script setup lang="ts">
/**
 * ImmersiveCharacterStage — Left-side 2:3 vertical character cards
 *
 * Displays portraits of the protagonist and scene NPCs with active speaker auras,
 * health status, defeat tags, and quick click/hover interactions.
 */
import { ref } from 'vue'
import { getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  npcs: any[]
  activeSpeakers: Set<string>
}>()

const emit = defineEmits<{
  npcClick: [npc: any]
  npcHover: [entity: any, event: MouseEvent]
  npcLeave: []
  npcContextmenu: [npc: any, event: MouseEvent]
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

function isNpcSpeaking(npc: any): boolean {
  if (!npc || !props.activeSpeakers) return false
  const nameMatch = npc.name && props.activeSpeakers.has(npc.name.toLowerCase())
  const idMatch = npc.id && props.activeSpeakers.has(String(npc.id).toLowerCase())
  return Boolean(nameMatch || idMatch)
}
</script>

<template>
  <aside class="flex flex-col gap-2 shrink-0 overflow-y-auto w-20 sm:w-28 md:w-36 lg:w-44 custom-scrollbar pr-1 py-1 max-h-full">
    <TransitionGroup name="npc-stage" tag="div" class="flex flex-col gap-2 w-full">
      <div
        v-for="npc in props.npcs"
        :key="npc.id"
        class="relative group flex flex-col items-center bg-slate-950 rounded-xl border-2 transition-all duration-300 shrink-0 w-full aspect-[2/3] overflow-hidden cursor-pointer shadow-[0_6px_20px_rgba(0,0,0,0.7)] active:scale-98"
        :class="[
          isNpcSpeaking(npc)
            ? 'border-amber-400 shadow-[0_0_25px_rgba(251,191,36,0.6)] ring-2 ring-amber-400/60'
            : npc.id === 'PLAYER'
              ? 'border-emerald-500/70 hover:border-emerald-400'
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
          <i :class="['ra text-4xl mb-1', npc.id === 'PLAYER' ? 'ra-player text-emerald-400' : 'ra-helmet text-cyan-400']"></i>
        </div>

        <!-- Active Speaker Badge -->
        <div v-if="isNpcSpeaking(npc)" class="absolute top-2 right-2 z-20 px-1.5 py-0.5 rounded-full bg-amber-500 text-black text-[8px] font-black uppercase tracking-wider shadow-md animate-bounce">
          Speaking
        </div>

        <!-- Hero Tag for Player -->
        <div v-else-if="npc.id === 'PLAYER'" class="absolute top-2 left-2 z-20 px-1.5 py-0.5 rounded-full bg-emerald-500/80 text-white backdrop-blur-md border border-emerald-300/40 text-[8px] font-black uppercase tracking-wider shadow-md">
          You
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

.npc-stage-move,
.npc-stage-enter-active,
.npc-stage-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.npc-stage-enter-from,
.npc-stage-leave-to {
  opacity: 0;
  transform: scale(0.92);
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
