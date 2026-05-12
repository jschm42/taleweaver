<script setup lang="ts">
import { configState } from '@/store/config'

defineProps<{
  activeSection?: string
  isGameView?: boolean
}>()
</script>

<template>
  <div v-if="configState.isLoaded && !configState.hasLlmConfig && activeSection !== 'profile'" 
       class="mb-8 p-6 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex flex-col md:flex-row items-center justify-between gap-6 animate-pulse-subtle shadow-xl shadow-amber-500/5">
    <div class="flex items-center gap-5">
      <div class="w-14 h-14 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-500 text-2xl shadow-lg shadow-amber-500/10">
        <i class="ra ra-warning"></i>
      </div>
      <div>
        <h3 class="text-amber-500 font-black uppercase tracking-widest text-sm mb-1">
          Configuration Required
        </h3>
        <p class="text-slate-400 text-sm max-w-xl">
          <span class="text-amber-400 font-bold">Intelligence is not configured!</span>
          This is mandatory to generate or play adventures.
          Please configure your AI providers in the administration settings to unlock the full experience.
        </p>
      </div>
    </div>
    <router-link to="/admin" class="px-6 py-3 rounded-xl bg-amber-500 text-slate-950 font-black text-xs uppercase tracking-[0.2em] hover:bg-amber-400 transition-all shadow-lg shadow-amber-500/20 whitespace-nowrap">
      Configure Now
    </router-link>
  </div>
</template>
