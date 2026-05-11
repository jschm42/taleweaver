<script setup lang="ts">
import { ref } from 'vue'
import type { CatalogTile } from '@/types'

const props = defineProps<{
  isOpen: boolean
  data: { type: 'styles' | 'tones', item: CatalogTile, index: number } | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'generate', payload: { type: 'styles' | 'tones', item: CatalogTile, index: number, prompt: string }): void
}>()

const customPrompt = ref('')

const handleGenerate = () => {
  if (props.data && customPrompt.value.trim()) {
    emit('generate', { 
      type: props.data.type, 
      item: props.data.item, 
      index: props.data.index, 
      prompt: customPrompt.value 
    })
    customPrompt.value = ''
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="emit('close')"></div>
      <div class="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl p-8 animate-fade-in">
        <h2 class="text-xl font-bold text-white mb-6 flex items-center gap-3">
          <i class="ra ra-quill-ink text-blue-500"></i>
          Custom Image Generation
        </h2>
        <p class="text-slate-400 text-sm mb-4">Provide a specific prompt for the profile image of <strong>{{ data?.item.name }}</strong>.</p>
        <textarea v-model="customPrompt" rows="4" placeholder="A dark moody oil painting of..." class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-blue-500/50 outline-none resize-none mb-6"></textarea>
        <div class="flex gap-4">
          <button @click="emit('close')" class="flex-1 py-3 border border-slate-800 text-slate-400 hover:text-white rounded-xl transition-colors font-bold">Cancel</button>
          <button 
            @click="handleGenerate" 
            :disabled="!customPrompt.trim()"
            class="flex-grow py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-all font-bold shadow-lg shadow-blue-900/20 disabled:opacity-50"
          >
            Generate
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
