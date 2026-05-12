<script setup lang="ts">
import { X, AlertTriangle, ShieldAlert, Zap } from 'lucide-vue-next'
import { configState } from '@/store/config'

defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div v-if="isOpen" class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div class="relative w-full max-w-lg bg-[#0d1117] border border-amber-500/30 rounded-3xl shadow-[0_0_50px_rgba(245,158,11,0.15)] overflow-hidden">
        <!-- Decoration -->
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-amber-500 to-transparent"></div>
        <div class="absolute -top-24 -right-24 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl"></div>
        <div class="absolute -bottom-24 -left-24 w-48 h-48 bg-amber-500/5 rounded-full blur-3xl"></div>

        <div class="p-8 relative">
          <!-- Header -->
          <div class="flex items-center justify-between mb-8">
            <div class="flex items-center gap-4">
              <div class="w-12 h-12 rounded-2xl bg-amber-500/20 flex items-center justify-center text-amber-500 shadow-inner">
                <ShieldAlert class="w-7 h-7" />
              </div>
              <div>
                <h2 class="text-xl font-black text-white uppercase tracking-tighter leading-none mb-1">Configuration Needed</h2>
                <p class="text-amber-500/60 text-[10px] font-bold uppercase tracking-[0.2em]">TaleWeaver Core Setup</p>
              </div>
            </div>
            <button 
              @click="emit('close')"
              class="w-10 h-10 rounded-full flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/5 transition-all"
            >
              <X class="w-6 h-6" />
            </button>
          </div>

          <!-- Content -->
          <div class="space-y-6">
            <!-- LLM Status -->
            <div 
              class="p-5 rounded-2xl border transition-all duration-500"
              :class="configState.hasLlmConfig ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/10 border-red-500/20'"
            >
              <div class="flex items-start gap-4">
                <div 
                  class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  :class="configState.hasLlmConfig ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'"
                >
                  <Zap class="w-5 h-5" />
                </div>
                <div>
                  <h4 class="text-sm font-black uppercase tracking-widest mb-1" :class="configState.hasLlmConfig ? 'text-emerald-400' : 'text-red-400'">
                    Intelligence (LLM)
                  </h4>
                  <p class="text-xs text-slate-400 leading-relaxed font-bold">
                    <span v-if="configState.hasLlmConfig">The Game Master is online and ready to weave your stories.</span>
                    <span v-else>The Game Master cannot think without a configured AI provider. This is <span class="text-red-400 underline underline-offset-2">mandatory</span> to play.</span>
                  </p>
                </div>
              </div>
            </div>

            <!-- T2I Status -->
            <div 
              class="p-5 rounded-2xl border transition-all duration-500"
              :class="configState.hasT2iConfig ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-amber-500/10 border-amber-500/20'"
            >
              <div class="flex items-start gap-4">
                <div 
                  class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  :class="configState.hasT2iConfig ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'"
                >
                  <AlertTriangle class="w-5 h-5" />
                </div>
                <div>
                  <h4 class="text-sm font-black uppercase tracking-widest mb-1" :class="configState.hasT2iConfig ? 'text-emerald-400' : 'text-amber-400'">
                    Visuals (Images)
                  </h4>
                  <p class="text-xs text-slate-400 leading-relaxed font-bold">
                    <span v-if="configState.hasT2iConfig">Visual generation is fully operational.</span>
                    <span v-else>You can play without images, but the experience will be text-only. Configure an image provider for the full immersion.</span>
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="mt-10 flex flex-col gap-3">
            <router-link 
              to="/admin" 
              class="w-full py-4 rounded-2xl bg-amber-500 text-slate-950 text-center font-black uppercase tracking-[0.2em] text-xs hover:bg-amber-400 transition-all shadow-xl shadow-amber-500/20 active:scale-[0.98]"
              @click="emit('close')"
            >
              Go to Settings
            </router-link>
            <button 
              @click="emit('close')"
              class="w-full py-4 rounded-2xl bg-white/5 text-slate-400 font-black uppercase tracking-[0.2em] text-[10px] hover:text-white hover:bg-white/10 transition-all"
            >
              Maybe Later
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.animate-pulse-subtle {
  animation: pulse-subtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse-subtle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}
</style>
