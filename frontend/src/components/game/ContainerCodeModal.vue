<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  title: string
  busy?: boolean
  errorMessage?: string
}>()

const emit = defineEmits<{
  close: []
  submit: [code: string]
}>()

const code = ref('')

watch(() => props.open, (open) => {
  if (open) {
    code.value = ''
  }
})

const onSubmit = () => {
  emit('submit', code.value)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[140] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-md bg-slate-900 border border-slate-700/60 rounded-3xl shadow-2xl overflow-hidden">
          <div class="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
            <div>
              <p class="text-[10px] uppercase tracking-[0.25em] text-amber-400 font-black">Locked Container</p>
              <h3 class="text-xl font-black text-white mt-1">{{ title }}</h3>
            </div>
            <button class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors" @click="emit('close')">
              <i class="ra ra-cancel"></i>
            </button>
          </div>

          <div class="p-6 space-y-4">
            <p class="text-sm text-slate-300">Enter the access code to unlock this container.</p>
            <input
              v-model="code"
              maxlength="32"
              class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white font-bold tracking-wider focus:border-amber-500/60 outline-none"
              placeholder="Enter code"
              @keyup.enter="onSubmit"
            />
            <p v-if="errorMessage" class="text-sm text-amber-300 leading-relaxed">
              {{ errorMessage }}
            </p>
          </div>

          <div class="px-6 pb-6 pt-2 flex gap-3 justify-end border-t border-slate-800/80">
            <button
              class="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
              @click="emit('close')"
            >
              Cancel
            </button>
            <button
              class="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold transition-colors disabled:opacity-50"
              :disabled="busy || !code.trim()"
              @click="onSubmit"
            >
              Unlock
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
