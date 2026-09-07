<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'

const props = defineProps<{
  title: string
  storyIdea: string
}>()

const emit = defineEmits<{
  (e: 'update:title', value: string): void
  (e: 'update:storyIdea', value: string): void
}>()
</script>

<template>
  <div class="space-y-4 bg-slate-950/40 p-4 sm:p-5 rounded-2xl border border-white/5">
    <!-- Title Input -->
    <div>
      <div class="flex items-center justify-between mb-1.5">
        <label class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-1.5">
          <span>Adventure Title</span>
          <span class="text-cyan-400">*</span>
        </label>
        <span class="text-[10px] font-mono font-bold text-slate-500">
          {{ props.title.length }}/50
        </span>
      </div>
      <input
        :value="props.title"
        @input="emit('update:title', ($event.target as HTMLInputElement).value)"
        type="text"
        maxlength="50"
        placeholder="e.g., Orbital Void: Protocol Omega"
        class="w-full px-3.5 sm:px-4 py-2.5 sm:py-3 bg-slate-900/90 border border-slate-700/80 rounded-xl text-white font-bold placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 transition-all text-xs sm:text-sm"
      />
    </div>

    <!-- Story Blueprint Input -->
    <div>
      <div class="flex items-center justify-between mb-1.5">
        <label class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-1.5">
          <Sparkles class="w-3.5 h-3.5 text-cyan-400" />
          <span>Story Blueprint & World Vision</span>
        </label>
      </div>
      <textarea
        :value="props.storyIdea"
        @input="emit('update:storyIdea', ($event.target as HTMLTextAreaElement).value)"
        rows="3"
        placeholder="Describe the atmosphere, mystery, factions, and world setting..."
        class="w-full px-3.5 sm:px-4 py-2.5 sm:py-3 bg-slate-900/90 border border-slate-700/80 rounded-xl text-white text-xs sm:text-sm placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 transition-all resize-none custom-scrollbar"
      ></textarea>
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
