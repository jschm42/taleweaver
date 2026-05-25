<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'

defineProps<{
  adventure: any
  adventureId: string
  coverSourceName: string
  isGenerating?: boolean
}>()

const emit = defineEmits<{
  (e: 'go-back'): void
  (e: 'stop-generation'): void
}>()
</script>

<template>
  <header class="bg-slate-900/40 border-b border-white/5 px-8 py-3 flex items-center backdrop-blur-2xl sticky top-0 z-40 shadow-2xl">
    <div class="flex items-center gap-6">
      <button 
        @click="emit('go-back')" 
        class="flex items-center gap-3 px-5 py-2.5 rounded-xl bg-slate-800/60 hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/50 transition-all duration-300 shadow-xl group active:scale-95"
      >
        <ArrowLeft class="w-4 h-4 text-emerald-500 group-hover:text-emerald-400 transition-colors" />
        <span class="text-xs font-black uppercase tracking-[0.2em] text-white transition-colors">Back</span>
      </button>
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-xl font-black text-white tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
            {{ adventure?.title || 'Adventure Editor' }}
          </h1>
          <span class="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-400 uppercase tracking-widest">Editor</span>
        </div>
        <p class="text-xs text-slate-500 font-mono uppercase tracking-tighter">Instance: {{ adventureId }}</p>
        <p v-if="coverSourceName" class="text-[11px] text-amber-300 font-bold uppercase tracking-widest mt-1">
          Cover of: {{ coverSourceName }}
        </p>
      </div>
    </div>
    
    <button
      v-if="isGenerating"
      @click="emit('stop-generation')"
      class="ml-auto flex items-center gap-2 px-5 py-2.5 rounded-xl bg-rose-600/90 hover:bg-rose-500 border border-rose-500/30 hover:border-rose-400 transition-all duration-300 shadow-lg animate-pulse hover:animate-none active:scale-95 group"
    >
      <i class="ra ra-cancel text-white group-hover:rotate-90 transition-transform duration-300"></i>
      <span class="text-xs font-black uppercase tracking-widest text-white">Stop Generation</span>
    </button>
  </header>
</template>
