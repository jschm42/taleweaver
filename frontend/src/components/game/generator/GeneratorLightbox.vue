<script setup lang="ts">
import { X } from 'lucide-vue-next'

const props = defineProps<{
  imageUrl: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <div
    v-if="props.imageUrl"
    class="fixed inset-0 z-[200] bg-black/90 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 cursor-pointer animate-fade-in"
    @click="emit('close')"
  >
    <div
      class="relative max-w-3xl max-h-[88vh] sm:max-h-[85vh] p-2 bg-slate-900 border border-cyan-500/30 rounded-2xl shadow-2xl flex flex-col items-center"
      @click.stop
    >
      <button
        class="absolute top-3 right-3 p-2 rounded-xl bg-black/70 text-white hover:bg-white/20 transition-colors z-10 min-w-[36px] min-h-[36px] flex items-center justify-center"
        @click="emit('close')"
        title="Close Preview"
      >
        <X class="w-5 h-5" />
      </button>
      <img
        :src="props.imageUrl"
        alt="Enlarged Artwork Preview"
        class="max-w-full max-h-[80vh] object-contain rounded-xl"
      />
    </div>
  </div>
</template>
