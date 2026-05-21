<script setup lang="ts">
const props = defineProps<{
  open: boolean
  title: string
  format: string
  content: string
  imageUrl?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const formatLabel = (value: string) => {
  const normalized = String(value || '').toUpperCase()
  if (!normalized) return 'DOCUMENT'
  if (['DOCUMENT', 'SCROLL', 'BOOK', 'SIGN'].includes(normalized)) return normalized
  return 'DOCUMENT'
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-[120] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="emit('close')" />

        <div class="relative z-10 w-full max-w-2xl max-h-[85vh] overflow-hidden rounded-3xl border border-slate-700 bg-slate-950 shadow-2xl flex flex-col">
          <div class="flex items-center justify-between px-6 py-4 border-b border-slate-800">
            <div class="min-w-0">
              <h3 class="text-lg font-black uppercase tracking-wide text-amber-100 truncate">{{ title }}</h3>
              <p class="text-[10px] uppercase tracking-[0.2em] text-amber-400/80 mt-1">{{ formatLabel(format) }}</p>
            </div>
            <button
              class="p-2 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              @click="emit('close')"
              title="Close"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="overflow-y-auto p-6 space-y-4">
            <div v-if="imageUrl" class="w-full h-44 rounded-2xl overflow-hidden border border-slate-800">
              <img :src="imageUrl" class="w-full h-full object-cover" />
            </div>

            <div class="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
              <p class="text-sm text-amber-50/90 leading-relaxed whitespace-pre-wrap">{{ content || 'No text content found.' }}</p>
            </div>
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
</style>
