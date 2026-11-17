<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'

const ef = useEntityFormContext()
</script>

<template>

  <!-- NPC Movement Configuration (Moveable & Allowed Scenes) -->
  <div v-if="ef.type === 'npc'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-4">
    <div class="flex items-center justify-between">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-slate-200 uppercase tracking-widest flex items-center gap-1.5">
          <i class="ra ra-footsteps text-sky-400"></i> Moveable (Scene Traversal)
        </p>
        <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
          Allows this NPC to move between scenes during the session. The GM decides when to move them.
        </p>
      </div>
      <button
        type="button"
        @click="ef.localForm.moveable = !ef.localForm.moveable"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1 shrink-0', ef.localForm.moveable ? 'bg-sky-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.moveable ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>

    <!-- Allowed Scenes selector if moveable is enabled -->
    <div v-if="ef.localForm.moveable" class="pt-3 border-t border-white/5 space-y-2">
      <div class="flex items-center justify-between">
        <p class="text-[11px] font-black text-slate-300 uppercase tracking-wider">Permitted Scenes</p>
        <span class="text-[9px] text-sky-400 font-mono font-bold">
          {{ (ef.localForm.allowed_scenes_input || []).length === 0 ? 'All scenes allowed' : `${(ef.localForm.allowed_scenes_input || []).length} scenes restricted` }}
        </span>
      </div>
      <p class="text-[10px] text-slate-500 leading-snug">
        Specify the scenes this NPC is allowed to move between. If none are selected, the NPC may traverse all rooms.
      </p>

      <div v-if="ef.sceneReferenceOptions.length" class="grid grid-cols-1 sm:grid-cols-2 gap-1.5 mt-2 max-h-40 overflow-y-auto custom-scrollbar p-1">
        <label
          v-for="s in ef.sceneReferenceOptions"
          :key="s.id"
          class="flex items-center gap-2 p-2 rounded-xl border text-xs cursor-pointer transition-all"
          :class="ef.isSceneAllowed(s.id) ? 'bg-sky-500/15 border-sky-500/40 text-sky-200 shadow-sm' : 'bg-slate-900/60 border-white/5 text-slate-400 hover:border-white/20'"
        >
          <input
            type="checkbox"
            :checked="ef.isSceneAllowed(s.id)"
            @change="ef.toggleAllowedScene(s.id)"
            class="rounded border-slate-700 text-sky-500 focus:ring-0"
          />
          <span class="truncate font-semibold text-[11px]">{{ s.name || s.id }}</span>
          <span class="text-[9px] font-mono text-slate-500 truncate ml-auto">({{ s.id }})</span>
        </label>
      </div>
      <p v-else class="text-[10px] text-slate-500 italic">No scenes found in this adventure.</p>
    </div>
  </div>
</template>
