<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Sliders, X, BrainCircuit, Sparkles } from 'lucide-vue-next'

const props = defineProps<{
  initialTurns?: number
  initialCompression?: boolean
  isSaving?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', payload: { turns: number; enableCompression: boolean }): void
}>()

const turns = ref(30)
const enableCompression = ref(true)

onMounted(() => {
  if (typeof props.initialTurns === 'number' && props.initialTurns >= 1) {
    turns.value = Math.min(100, Math.max(1, props.initialTurns))
  }
  if (typeof props.initialCompression === 'boolean') {
    enableCompression.value = props.initialCompression
  }
})

const tokenProfile = computed(() => {
  if (turns.value <= 15) {
    return {
      label: 'Low Token Cost',
      class: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
      description: 'Minimum token consumption per turn. Great for lightweight sessions with fast responses, but older details will fade quickly.'
    }
  }
  if (turns.value <= 40) {
    return {
      label: 'Balanced (Standard)',
      class: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
      description: 'Default setting (30 turns). Balances rich narrative continuity across scenes with moderate, predictable token usage.'
    }
  }
  return {
    label: 'Deep Memory',
    class: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
    description: 'Extensive narrative recall over many turns. Best for intricate plots, but will consume significantly more LLM tokens each turn.'
  }
})

function handleInput(event: Event) {
  const raw = Number((event.target as HTMLInputElement).value)
  if (!isNaN(raw)) {
    turns.value = Math.min(100, Math.max(1, raw))
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fade-in" @click.self="emit('close')">
    <div class="w-full max-w-lg rounded-3xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden" @click.stop>
      <!-- Header -->
      <div class="px-6 py-5 border-b border-white/10 flex items-center justify-between bg-slate-950/40">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0 shadow-inner">
            <Sliders class="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h3 class="text-base sm:text-lg font-black text-white font-display uppercase tracking-wider">Session Memory & Settings</h3>
            <p class="text-xs text-slate-400">Configure LLM context memory for this active session.</p>
          </div>
        </div>
        <button 
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors"
          @click="emit('close')"
          title="Close"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Content -->
      <div class="px-6 py-6 flex flex-col gap-6">
        <!-- Memory Turns Slider Panel -->
        <div class="space-y-4">
          <div class="flex justify-between items-start gap-4">
            <div>
              <label class="block text-xs font-black uppercase tracking-widest text-slate-300">Narrator Turn Memory</label>
              <p class="text-xs text-slate-400 mt-1">
                Number of past turns passed to the narrator in this session.
              </p>
            </div>
            <div class="flex items-center gap-2 bg-black/60 border border-white/15 px-3 py-1.5 rounded-xl shrink-0">
              <input
                type="number"
                min="1"
                max="100"
                :value="turns"
                @input="handleInput"
                class="w-12 bg-transparent text-center text-white font-mono font-bold text-sm focus:outline-none"
              />
              <span class="text-[11px] font-bold text-amber-400 uppercase tracking-wider">Turns</span>
            </div>
          </div>

          <!-- Slider -->
          <div class="space-y-2 pt-2">
            <input
              type="range"
              min="1"
              max="100"
              :value="turns"
              @input="handleInput"
              class="w-full accent-amber-500 cursor-pointer h-2 bg-slate-800 rounded-lg"
            />
            <div class="flex justify-between items-center text-[10px] text-slate-500 uppercase tracking-widest">
              <span>1 Turn</span>
              <span class="text-amber-400 font-bold">30 Default</span>
              <span>100 Turns</span>
            </div>
          </div>

          <!-- Token Impact Profile Badge & Explanation -->
          <div :class="['rounded-2xl border p-4 space-y-2 transition-all', tokenProfile.class]">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <BrainCircuit class="w-4 h-4" />
                <span class="text-xs font-black uppercase tracking-wider">{{ tokenProfile.label }}</span>
              </div>
              <span class="text-[11px] font-mono font-bold">{{ turns }} / 100 turns</span>
            </div>
            <p class="text-xs opacity-90 leading-relaxed">
              {{ tokenProfile.description }}
            </p>
          </div>
        </div>

        <!-- Automatic History Compression Checkbox/Toggle -->
        <div class="flex items-start justify-between gap-4 p-4 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all">
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <label class="block text-xs font-black uppercase tracking-widest text-slate-200 cursor-pointer" @click="enableCompression = !enableCompression">
                Automatic History Compression
              </label>
              <span class="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/30">
                English
              </span>
            </div>
            <p class="text-xs text-slate-400 leading-relaxed">
              When turns exceed the memory limit, older turns are automatically compressed into an English chronicle summary and passed to the narrator.
            </p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer shrink-0 mt-0.5">
            <input type="checkbox" v-model="enableCompression" class="sr-only peer">
            <div class="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500 peer-checked:after:bg-white"></div>
          </label>
        </div>

        <!-- Helpful tip note -->
        <div class="flex items-start gap-3 p-3.5 rounded-xl bg-white/[0.03] border border-white/5 text-slate-400 text-xs leading-relaxed">
          <Sparkles class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <span>
            Changes take effect immediately on your next action. Intermediate game events (such as dice rolls) are formatted automatically without consuming extra turns.
          </span>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-white/10 flex justify-end gap-3 bg-slate-950/40">
        <button
          type="button"
          class="px-4 py-2 rounded-xl border border-white/15 text-slate-300 text-xs font-bold uppercase tracking-wider hover:bg-white/5 transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          type="button"
          class="px-5 py-2 rounded-xl bg-amber-500 text-slate-950 text-xs font-black uppercase tracking-widest hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg shadow-amber-500/20 cursor-pointer"
          :disabled="props.isSaving"
          @click="emit('save', { turns, enableCompression })"
        >
          <span v-if="props.isSaving" class="w-4 h-4 border-2 border-slate-950/30 border-t-slate-950 rounded-full animate-spin"></span>
          {{ props.isSaving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.2s ease-out forwards;
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}
</style>
