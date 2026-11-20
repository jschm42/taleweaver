<script setup lang="ts">
/**
 * DebugNpcTile — compact NPC tile of the debug inspector: portrait, name, ID, status, location
 * and HP. Clicking it opens DebugNpcDetailDialog with everything else.
 */
import { computed } from 'vue'
import { Compass, EyeOff, Users } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const props = defineProps<{ npc: any }>()
const emit = defineEmits<{ open: [] }>()

const hpPercent = computed(() => Math.min(100, Math.max(0, (props.npc.hp / (props.npc.max_hp || 100)) * 100)))
const hpClass = computed(() => (hpPercent.value > 50 ? 'bg-emerald-500' : hpPercent.value > 20 ? 'bg-amber-500' : 'bg-red-500'))
</script>

<template>
  <button
    type="button"
    class="w-full text-left rounded-2xl border bg-slate-900/90 p-3 flex items-center gap-3 transition-all shadow-lg cursor-pointer hover:border-cyan-400/60 hover:bg-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
    :class="[
      npc.is_in_current_scene ? 'border-cyan-500/50 ring-1 ring-cyan-500/30' : 'border-slate-800',
      !npc.is_alive ? 'opacity-60 grayscale-[0.4]' : '',
    ]"
    :aria-label="`Show details of ${npc.name}`"
    @click="emit('open')"
  >
    <div class="relative w-12 h-12 rounded-xl overflow-hidden bg-slate-950 border border-slate-700/80 shrink-0">
      <img v-if="npc.image_url" :src="getImageUrl(npc.image_url)" class="w-full h-full object-cover object-center" :alt="npc.name" />
      <div v-else class="w-full h-full flex items-center justify-center text-slate-600">
        <Users class="w-5 h-5" />
      </div>
      <span
        v-if="npc.is_in_current_scene"
        class="absolute bottom-0 inset-x-0 bg-cyan-500 text-slate-950 text-[8px] font-black uppercase text-center tracking-tighter"
      >
        Here
      </span>
    </div>

    <div class="flex-1 min-w-0 space-y-1">
      <div class="flex items-center justify-between gap-2">
        <h4 class="text-sm font-black text-white truncate">{{ npc.name }}</h4>
        <span class="flex items-center gap-1 shrink-0">
          <EyeOff v-if="npc.is_hidden" class="w-3 h-3 text-amber-400" aria-label="Hidden" />
          <span
            class="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider"
            :class="npc.is_alive ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-red-500/20 text-red-300 border border-red-500/30'"
          >
            {{ npc.is_alive ? 'Alive' : 'Defeated' }}
          </span>
        </span>
      </div>
      <div class="flex items-center gap-2 text-[10px] text-slate-400 min-w-0">
        <span class="font-mono truncate">{{ npc.id }}</span>
        <span class="flex items-center gap-1 truncate text-slate-300">
          <Compass class="w-3 h-3 text-cyan-400 shrink-0" />
          <span class="truncate">{{ npc.current_scene_name || npc.current_scene_id }}</span>
        </span>
      </div>
      <div class="flex items-center gap-2">
        <div class="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
          <div class="h-full transition-all duration-300" :class="hpClass" :style="{ width: `${hpPercent}%` }"></div>
        </div>
        <span class="text-[10px] font-mono text-slate-400 shrink-0">{{ npc.hp }}/{{ npc.max_hp }}</span>
      </div>
    </div>
  </button>
</template>
