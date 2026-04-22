<script setup lang="ts">
const props = defineProps<{
  open: boolean
  data: any | null
}>()

const emit = defineEmits<{
  close: []
  reveal: []
  hint: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-[220] bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4" @click.self="emit('close')">
        <div class="w-full max-w-3xl max-h-[85vh] overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl flex flex-col">
          <header class="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
            <div>
              <p class="text-[10px] uppercase tracking-[0.2em] text-fuchsia-400/70 font-black">Secret Utility</p>
              <h2 class="text-xl text-slate-100 font-bold">Walkthrough</h2>
            </div>
            <button class="text-slate-400 hover:text-white" @click="emit('close')">Close</button>
          </header>

          <div class="p-5 overflow-y-auto custom-scrollbar space-y-4">
            <div class="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <p class="text-xs uppercase tracking-widest text-slate-400 font-black">XP</p>
                <p class="text-lg font-black text-amber-300 tabular-nums">{{ data?.current_xp ?? 0 }}</p>
              </div>
              <p class="mt-3 text-sm text-slate-300 leading-relaxed">{{ data?.preview || data?.message || 'No walkthrough available.' }}</p>
            </div>

            <div v-if="!data?.available" class="rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-slate-400 text-sm">
              No walkthrough available for this adventure yet.
            </div>

            <div v-else-if="!data?.revealed" class="rounded-xl border border-fuchsia-500/20 bg-fuchsia-500/5 p-4">
              <p class="text-sm text-fuchsia-200 mb-3">The full strategy is sealed. Reveal it to unlock all steps.</p>
              <button
                class="px-4 py-2 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-500 text-white text-sm font-bold transition-colors"
                @click="emit('reveal')"
              >
                Reveal Walkthrough ({{ data?.reveal_cost ?? 200 }} XP)
              </button>
            </div>

            <div v-else class="space-y-3">
              <div class="flex items-center justify-between gap-3 flex-wrap">
                <p class="text-sm font-bold text-emerald-300">Walkthrough Unlocked</p>
                <button
                  class="px-3 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition-colors"
                  @click="emit('hint')"
                >
                  Buy Hint ({{ data?.hint_cost ?? 50 }} XP)
                </button>
              </div>

              <ol class="space-y-2">
                <li v-for="(step, index) in data?.steps || []" :key="index" class="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p class="text-[10px] uppercase tracking-widest text-slate-500 font-black">Step {{ index + 1 }}</p>
                  <p class="text-sm text-slate-100 font-bold mt-1">{{ step.title }}</p>
                  <p class="text-sm text-slate-300 mt-1 leading-relaxed">{{ step.content }}</p>
                </li>
              </ol>
            </div>

            <div v-if="data?.latest_hint" class="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
              <p class="text-[10px] uppercase tracking-widest text-amber-300 font-black">Latest Hint</p>
              <p class="text-sm text-amber-100 mt-1">{{ data.latest_hint }}</p>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: 3px; }
</style>
