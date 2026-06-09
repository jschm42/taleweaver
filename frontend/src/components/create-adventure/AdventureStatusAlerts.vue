<script setup lang="ts">
import { configState } from '@/store/config'

defineProps<{
  errorMsg: string
  hasLlmConfig: boolean
  hasT2iConfig: boolean
  isLoadingCatalogs: boolean
}>()
</script>

<template>
  <div>
    <!-- Error Message -->
    <div v-if="errorMsg" class="mb-6 md:mb-8 p-3.5 sm:p-4 rounded-2xl border border-red-500/30 bg-red-500/10 text-red-300 text-sm flex items-center gap-3">
      <div class="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0"></div>
      <span class="break-words">{{ errorMsg }}</span>
    </div>

    <!-- CRITICAL: No LLM -->
    <div v-if="!hasLlmConfig && configState.isLoaded" class="mb-6 md:mb-8 p-4 sm:p-5 md:p-6 rounded-2xl border border-red-500/50 bg-red-500/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 md:gap-6">
      <div class="flex items-start sm:items-center gap-3 sm:gap-4 min-w-0">
        <div class="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-red-500/20 flex items-center justify-center text-red-500 text-lg sm:text-xl shrink-0">
          <i class="ra ra-warning"></i>
        </div>
        <div class="min-w-0">
          <h3 class="text-red-500 font-black uppercase tracking-widest text-xs mb-1">Intelligence Required</h3>
          <p class="text-slate-400 text-xs">No AI provider is configured for world generation. You cannot weave new realities without a connection.</p>
        </div>
      </div>
      <router-link to="/admin" class="self-stretch sm:self-auto text-center px-5 sm:px-6 py-2.5 sm:py-3 rounded-xl bg-red-600 text-white font-black text-xxs uppercase tracking-widest hover:bg-red-500 transition-all whitespace-nowrap">
        Go to Configuration
      </router-link>
    </div>

    <!-- Warning if no image model -->
    <div v-if="hasLlmConfig && !hasT2iConfig && !isLoadingCatalogs" class="mb-6 md:mb-8 p-3.5 sm:p-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 text-amber-300 text-sm flex items-center gap-3">
      <div class="w-2 h-2 rounded-full bg-amber-500 shrink-0"></div>
      <span class="break-words">Warning: No image generation model is configured. You can still generate the adventure, but visual assets will be skipped.</span>
    </div>
  </div>
</template>
