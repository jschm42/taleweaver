<script setup lang="ts">
import { configState } from '@/store/config'
import { isSetupWizardAvailable, openSetupWizard } from '@/store/setupWizard'

defineProps<{
  activeSection?: string
  isGameView?: boolean
}>()
</script>

<template>
  <!-- The server works, but this player must bring an own key (key policy). -->
  <div
    v-if="configState.isLoaded && configState.missingPersonalKeys.length && activeSection !== 'profile' && activeSection !== 'leaderboard'"
    class="mb-8 flex flex-col gap-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-6 md:flex-row md:items-center"
  >
    <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-xl text-amber-400">
      <i class="ra ra-key"></i>
    </div>
    <div class="min-w-0">
      <h3 class="mb-1 text-sm font-black uppercase tracking-widest text-amber-400">Your own API key is needed</h3>
      <p v-for="item in configState.missingPersonalKeys" :key="item.id" class="text-sm text-slate-300">{{ item.message }}</p>
    </div>
  </div>
  <div v-else-if="configState.isLoaded && !configState.hasLlmConfig && activeSection !== 'profile' && activeSection !== 'leaderboard'" 
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
    <button
      v-if="isSetupWizardAvailable"
      type="button"
      class="px-6 py-3 rounded-xl bg-amber-500 text-slate-950 font-black text-xs uppercase tracking-[0.2em] hover:bg-amber-400 transition-all shadow-lg shadow-amber-500/20 whitespace-nowrap"
      @click="openSetupWizard"
    >
      Configure Now
    </button>
    <span v-else class="text-xs font-bold text-amber-400/80 uppercase tracking-widest whitespace-nowrap">
      Ask an administrator
    </span>
  </div>
</template>
