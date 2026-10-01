<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'

const props = defineProps<{
  title: string
  storyIdea: string
  generationStrictness?: string
}>()

const emit = defineEmits<{
  (e: 'update:title', value: string): void
  (e: 'update:storyIdea', value: string): void
  (e: 'update:generationStrictness', value: string): void
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
        <div class="flex items-center gap-2">
          <label class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-1.5">
            <Sparkles class="w-3.5 h-3.5 text-cyan-400" />
            <span>Story Blueprint & World Vision</span>
          </label>
          <InfoPopoverButton title="Structured Syntax">
            <p class="mb-2">Use structured tags to guide the AI linearly (Limit: 30 sequences) or force specific entities.</p>
            <div class="space-y-1 mb-2 font-mono text-cyan-400">
              <div>[Sequence: 1] Sequence descriptions</div>
              <div>[Scene: 1] Scene descriptions</div>
              <div>[NPC: 1] NPC description</div>
              <div>[Scene: 2] Scene descriptions</div>
              <div>[NPC: 2] NPC description</div>
              <div>[Sequence: 2] ...</div>
            </div>
            <p class="mb-2">Enable <b>Strict Adherence</b> Builder Mode to enforce the structure.</p>
            <p class="text-[10px] text-slate-400 italic">See /docs/world-builder-syntax.md for the full guide.</p>
          </InfoPopoverButton>
        </div>
      </div>
      <textarea
        :value="props.storyIdea"
        @input="emit('update:storyIdea', ($event.target as HTMLTextAreaElement).value)"
        rows="3"
        placeholder="Describe the atmosphere, mystery, factions, and world setting..."
        class="w-full px-3.5 sm:px-4 py-2.5 sm:py-3 bg-slate-900/90 border border-slate-700/80 rounded-xl text-white text-xs sm:text-sm placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 transition-all resize-none custom-scrollbar"
      ></textarea>
    </div>

    <!-- World-Builder Strictness -->
    <div>
      <div class="flex items-center justify-between mb-1.5">
        <label class="text-xs font-black uppercase tracking-widest text-slate-300 flex items-center gap-1.5">
          <span>Builder Mode</span>
        </label>
      </div>
      <div class="flex gap-2">
        <button
          type="button"
          @click="emit('update:generationStrictness', 'strict')"
          :class="[
            'flex-1 px-3 py-2 rounded-xl text-xs font-bold transition-all border',
            props.generationStrictness === 'strict'
              ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 shadow-[0_0_10px_rgba(6,182,212,0.1)]'
              : 'bg-slate-900/50 border-slate-700/50 text-slate-400 hover:bg-slate-800'
          ]"
        >
          Strict Adherence
        </button>
        <button
          type="button"
          @click="emit('update:generationStrictness', 'creative')"
          :class="[
            'flex-1 px-3 py-2 rounded-xl text-xs font-bold transition-all border',
            props.generationStrictness === 'creative'
              ? 'bg-purple-500/20 border-purple-500/50 text-purple-300 shadow-[0_0_10px_rgba(168,85,247,0.1)]'
              : 'bg-slate-900/50 border-slate-700/50 text-slate-400 hover:bg-slate-800'
          ]"
        >
          Creative Expansion
        </button>
      </div>
      <p class="text-[10px] text-slate-500 mt-1.5 leading-relaxed">
        <template v-if="props.generationStrictness === 'strict'">
          The Architect strictly implements your structural blueprint tags like <span class="font-mono text-cyan-400">[Sequence: ...]</span> or <span class="font-mono text-cyan-400">[Scene: ...]</span>.
        </template>
        <template v-else>
          The Architect expands creatively on your blueprint and fills in the gaps freely.
        </template>
      </p>
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
