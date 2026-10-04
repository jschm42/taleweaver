<script setup lang="ts">
/**
 * ExitSessionModal — Confirmation dialog when player chooses to leave the active game session.
 */
import { onBeforeUnmount, onMounted } from 'vue'
import { LogOut, X, ShieldCheck } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  adventureTitle?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', handleKeyDown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeyDown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[120] bg-black/80 backdrop-blur-md flex items-center justify-center p-4 select-none"
        @click.self="emit('close')"
      >
        <div
          class="w-full max-w-md bg-slate-900/95 border border-slate-700/80 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.8)] overflow-hidden flex flex-col transition-all animate-modal-pop"
        >
          <!-- Header -->
          <div class="px-5 py-4 border-b border-white/10 flex items-center justify-between bg-slate-950/60">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
                <LogOut class="w-4 h-4" />
              </div>
              <div>
                <h3 class="text-sm font-black uppercase tracking-wider text-white">Leave Adventure</h3>
                <p class="text-[10px] text-slate-400 uppercase tracking-widest">Active Game Session</p>
              </div>
            </div>
            <button
              type="button"
              @click="emit('close')"
              class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
              title="Cancel"
            >
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Body -->
          <div class="p-5 space-y-4">
            <p class="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Are you sure you want to leave
              <strong v-if="adventureTitle" class="text-white">"{{ adventureTitle }}"</strong>
              <span v-else>this adventure</span>?
            </p>

            <div class="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-start gap-2.5 text-xs text-emerald-300">
              <ShieldCheck class="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
              <div class="space-y-0.5 leading-normal">
                <span class="font-bold block">Progress is safely archived</span>
                <span class="text-slate-400 text-[11px]">Your state, inventory, and timeline have been automatically saved. You can resume this session anytime from the Portal.</span>
              </div>
            </div>
          </div>

          <!-- Footer Actions -->
          <div class="px-5 py-3.5 bg-slate-950/60 border-t border-white/10 flex items-center justify-end gap-2.5">
            <button
              type="button"
              @click="emit('close')"
              class="px-4 py-2 rounded-xl border border-white/10 hover:border-white/20 bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-bold transition-all cursor-pointer"
            >
              Stay in Game
            </button>
            <button
              type="button"
              @click="emit('confirm')"
              class="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-950/40 transition-all cursor-pointer active:scale-95"
            >
              <LogOut class="w-3.5 h-3.5" />
              <span>Leave Session</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes modalPop {
  0% {
    transform: scale(0.95);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}
.animate-modal-pop {
  animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
