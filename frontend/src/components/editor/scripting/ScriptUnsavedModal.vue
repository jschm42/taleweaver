<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { TriangleAlert } from 'lucide-vue-next'

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'confirm'): void
}>()

function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  e.stopPropagation()
  emit('cancel')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[110] flex items-center justify-center p-6">
      <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-md" @click="emit('cancel')"></div>

      <div
        class="relative w-full max-w-md bg-[#0a1120] border border-amber-500/30 rounded-2xl shadow-2xl p-6 space-y-5"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="script-unsaved-title"
      >
        <div class="flex items-start gap-3">
          <TriangleAlert class="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h3 id="script-unsaved-title" class="text-lg font-black text-white tracking-tight">
              Unsaved changes
            </h3>
            <p class="text-slate-400 text-sm mt-1 leading-relaxed">
              The script has changes that were not saved. Loading another script will
              <span class="text-amber-300 font-bold">overwrite</span> them and they will be lost.
            </p>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3">
          <button
            type="button"
            class="px-5 py-2.5 rounded-xl text-slate-400 font-bold text-sm hover:text-white transition-colors"
            @click="emit('cancel')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-black text-xs uppercase tracking-widest transition-colors shadow-lg shadow-rose-600/20"
            @click="emit('confirm')"
          >
            Discard &amp; Overwrite
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
