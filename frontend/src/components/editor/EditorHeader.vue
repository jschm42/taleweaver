<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'

defineProps<{
  adventure: any
  adventureId: string
  coverSourceName: string
  activeTab: string
}>()

const emit = defineEmits<{
  (e: 'go-back'): void
  (e: 'update:activeTab', tab: any): void
}>()
</script>

<template>
  <header class="bg-slate-900/40 border-b border-white/5 px-8 py-3 flex justify-between items-center backdrop-blur-2xl sticky top-0 z-40 shadow-2xl">
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
    
    <div class="flex items-center gap-6">
      <nav class="flex bg-black/40 rounded-xl p-1 border border-white/5 backdrop-blur-md shadow-inner">
        <button 
          v-for="tab in (['physical', 'plot', 'advanced'] as const)" 
          :key="tab"
          @click="emit('update:activeTab', tab)"
          :class="[
            'px-4 py-1.5 text-xs font-black uppercase tracking-[0.2em] rounded-lg transition-all duration-300',
            activeTab === tab ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
          ]"
        >
          {{ tab }}
        </button>
      </nav>
    </div>
  </header>
</template>
