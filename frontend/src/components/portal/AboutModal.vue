<script setup lang="ts">
import { configState } from '@/store/config'

defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits(['close'])

const currentYear = new Date().getFullYear()
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div v-if="isOpen" class="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-[#02060c]/80 backdrop-blur-sm">
      <div 
        class="w-full max-w-lg bg-[#0a111c] border border-white/10 rounded-2xl shadow-2xl overflow-hidden relative"
        @click.stop
      >
        <!-- Decoration -->
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-aether-primary/50 via-purple-500/50 to-aether-primary/50"></div>
        
        <!-- Header -->
        <div class="px-8 pt-8 pb-6 text-center">
          <div class="inline-block p-4 rounded-2xl bg-white/5 border border-white/10 mb-4">
            <img src="@/assets/svg/app-logo.svg" class="w-12 h-12 drop-shadow-[0_0_10px_rgba(78,222,163,0.4)]" alt="Logo" />
          </div>
          <h2 class="text-3xl font-black text-white font-display tracking-tight mb-1">TaleWeaver</h2>
          <p class="text-aether-primary/60 text-xs font-bold uppercase tracking-[0.3em]">Chronicle Intelligence</p>
        </div>

        <!-- Content -->
        <div class="px-8 pb-8 space-y-6 max-h-[60vh] overflow-y-auto custom-scrollbar">
          <div class="space-y-4">
            <div class="flex items-center justify-between py-3 border-b border-white/5">
              <span class="text-xs font-black text-slate-500 uppercase tracking-widest">Version</span>
              <span class="text-xs font-bold text-white px-2 py-1 bg-white/5 rounded-lg border border-white/10">v{{ configState.appVersion }}</span>
            </div>
            
            <div class="flex items-center justify-between py-3 border-b border-white/5">
              <span class="text-xs font-black text-slate-500 uppercase tracking-widest">Copyright</span>
              <span class="text-xs font-bold text-slate-300">© {{ currentYear }} Jean Schmitz</span>
            </div>

            <div class="flex items-center justify-between py-3 border-b border-white/5">
              <span class="text-xs font-black text-slate-500 uppercase tracking-widest">License</span>
              <span class="text-xs font-bold text-aether-primary hover:underline cursor-help" title="MIT License: Free to use, modify, and distribute.">MIT License</span>
            </div>
          </div>

          <!-- Credits Section -->
          <div class="space-y-4">
            <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2 border-l-2 border-aether-primary pl-3">Credits & Acknowledgements</h3>
            
            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-1">
                <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest">AI & LLM</p>
                <p class="text-[11px] text-slate-300">Black Forest Labs (FLUX)</p>
                <p class="text-[11px] text-slate-300">LiteLLM Abstraction</p>
              </div>
              <div class="space-y-1">
                <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest">Voice & TTS</p>
                <p class="text-[11px] text-slate-300">Google Gemini TTS</p>
                <p class="text-[11px] text-slate-300">ElevenLabs</p>
              </div>
              <div class="space-y-1">
                <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest">Mapping</p>
                <p class="text-[11px] text-slate-300">Rough.js, Dagre</p>
              </div>
              <div class="space-y-1">
                <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest">Frameworks</p>
                <p class="text-[11px] text-slate-300">FastAPI, SQLAlchemy</p>
                <p class="text-[11px] text-slate-300">Vue.js, Vite, Tailwind</p>
              </div>
              <div class="space-y-1">
                <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest">Visual Assets</p>
                <p class="text-[11px] text-slate-300">Recraft.ai, DiceBear</p>
              </div>
              <div class="space-y-1">
                <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest">Iconography</p>
                <p class="text-[11px] text-slate-300">RPG-Awesome, Lucide</p>
              </div>
            </div>

            <div class="space-y-1">
              <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest">Typography</p>
              <p class="text-[11px] text-slate-300">Press Start 2P, Acme, Orbitron</p>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <p class="text-[11px] leading-relaxed text-slate-400 italic">
              "TaleWeaver is an advanced agentic storytelling engine, designed to weave infinite chronicles through the power of artificial intelligence. Every choice is a thread, every word a destiny."
            </p>
          </div>

          <div class="pt-4 flex justify-center sticky bottom-0 bg-[#0a111c] py-4">
            <button 
              @click="emit('close')"
              class="px-8 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-black text-white uppercase tracking-widest hover:bg-white/10 hover:border-white/20 transition-all"
            >
              Close Archive
            </button>
          </div>
        </div>
      </div>

      <!-- Backdrop click -->
      <div class="absolute inset-0 z-[-1]" @click="emit('close')"></div>
    </div>
  </Transition>
</template>
