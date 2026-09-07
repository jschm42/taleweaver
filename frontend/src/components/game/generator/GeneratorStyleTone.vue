<script setup lang="ts">
import { Flame, Palette, Image as ImageIcon } from 'lucide-vue-next'

interface OptionItem {
  id: string
  name: string
}

const props = defineProps<{
  selectedToneId: string
  selectedStyleId: string
  displayTones: OptionItem[]
  displayStyles: OptionItem[]
  generateSceneImages: boolean
  generateNpcImages: boolean
  generateItemImages: boolean
}>()

const emit = defineEmits<{
  (e: 'update:selectedToneId', val: string): void
  (e: 'update:selectedStyleId', val: string): void
  (e: 'update:generateSceneImages', val: boolean): void
  (e: 'update:generateNpcImages', val: boolean): void
  (e: 'update:generateItemImages', val: boolean): void
}>()
</script>

<template>
  <div class="space-y-4">
    <!-- Tone & Visual Style Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <!-- Tone Selector -->
      <div class="bg-slate-950/40 p-4 rounded-2xl border border-white/5 space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-1.5">
            <Flame class="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>Tone</span>
          </span>
          <span class="text-[10px] text-slate-400 uppercase font-bold truncate max-w-[120px] text-right">
            {{ props.selectedToneId || 'Select Tone' }}
          </span>
        </div>
        <div class="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto custom-scrollbar pr-1">
          <button
            v-for="t in props.displayTones"
            :key="t.id"
            type="button"
            @click="emit('update:selectedToneId', t.id)"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-bold transition-all min-h-[32px] flex items-center',
              props.selectedToneId === t.id
                ? 'bg-amber-500/20 border border-amber-500/60 text-amber-300 shadow-sm shadow-amber-500/20 ring-1 ring-amber-500/30'
                : 'bg-white/5 border border-white/5 text-slate-400 hover:text-white hover:bg-white/10 active:scale-95'
            ]"
          >
            {{ t.name }}
          </button>
        </div>
      </div>

      <!-- Style Selector -->
      <div class="bg-slate-950/40 p-4 rounded-2xl border border-white/5 space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-1.5">
            <Palette class="w-3.5 h-3.5 text-violet-400 shrink-0" />
            <span>Visual Art Style</span>
          </span>
          <span class="text-[10px] text-slate-400 uppercase font-bold truncate max-w-[120px] text-right">
            {{ props.selectedStyleId || 'Select Style' }}
          </span>
        </div>
        <div class="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto custom-scrollbar pr-1">
          <button
            v-for="s in props.displayStyles"
            :key="s.id"
            type="button"
            @click="emit('update:selectedStyleId', s.id)"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-bold transition-all capitalize min-h-[32px] flex items-center',
              props.selectedStyleId === s.id
                ? 'bg-violet-500/20 border border-violet-500/60 text-violet-300 shadow-sm shadow-violet-500/20 ring-1 ring-violet-500/30'
                : 'bg-white/5 border border-white/5 text-slate-400 hover:text-white hover:bg-white/10 active:scale-95'
            ]"
          >
            {{ s.name }}
          </button>
        </div>
      </div>
    </div>

    <!-- Visual Generation Toggles -->
    <div class="bg-slate-950/40 p-4 rounded-2xl border border-white/5 space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-2">
          <ImageIcon class="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span>AI Visual Generation</span>
        </span>
        <span class="text-[10px] text-slate-500 uppercase font-bold">Image Assets</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3">
        <!-- Scene Illustrations -->
        <button
          type="button"
          @click="emit('update:generateSceneImages', !props.generateSceneImages)"
          :class="[
            'p-3 rounded-xl border flex items-center justify-between transition-all text-left select-none active:scale-[0.98]',
            props.generateSceneImages
              ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 shadow-sm shadow-emerald-500/10'
              : 'bg-white/5 border-white/5 text-slate-500 hover:border-white/10'
          ]"
        >
          <div class="flex flex-col">
            <span class="text-xs font-bold">Scene Art</span>
            <span class="text-[10px] text-slate-500 font-normal">Atmospheric backdrops</span>
          </div>
          <div
            :class="[
              'w-2.5 h-2.5 rounded-full transition-all shrink-0 ml-2',
              props.generateSceneImages ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-slate-700'
            ]"
          ></div>
        </button>

        <!-- NPC Portraits -->
        <button
          type="button"
          @click="emit('update:generateNpcImages', !props.generateNpcImages)"
          :class="[
            'p-3 rounded-xl border flex items-center justify-between transition-all text-left select-none active:scale-[0.98]',
            props.generateNpcImages
              ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 shadow-sm shadow-emerald-500/10'
              : 'bg-white/5 border-white/5 text-slate-500 hover:border-white/10'
          ]"
        >
          <div class="flex flex-col">
            <span class="text-xs font-bold">NPC Portraits</span>
            <span class="text-[10px] text-slate-500 font-normal">Character visualizations</span>
          </div>
          <div
            :class="[
              'w-2.5 h-2.5 rounded-full transition-all shrink-0 ml-2',
              props.generateNpcImages ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-slate-700'
            ]"
          ></div>
        </button>

        <!-- Item Icons -->
        <button
          type="button"
          @click="emit('update:generateItemImages', !props.generateItemImages)"
          :class="[
            'p-3 rounded-xl border flex items-center justify-between transition-all text-left select-none active:scale-[0.98]',
            props.generateItemImages
              ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 shadow-sm shadow-emerald-500/10'
              : 'bg-white/5 border-white/5 text-slate-500 hover:border-white/10'
          ]"
        >
          <div class="flex flex-col">
            <span class="text-xs font-bold">Item Icons</span>
            <span class="text-[10px] text-slate-500 font-normal">Weapons & artifacts</span>
          </div>
          <div
            :class="[
              'w-2.5 h-2.5 rounded-full transition-all shrink-0 ml-2',
              props.generateItemImages ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-slate-700'
            ]"
          ></div>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 9999px;
}
</style>
