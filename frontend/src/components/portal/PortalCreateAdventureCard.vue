<script setup lang="ts">
const emit = defineEmits<{
  (e: 'create'): void
}>()
</script>

<template>
  <button
    class="group flex flex-col items-center justify-center border-2 border-dashed border-white/10 rounded-xl aspect-[3/2] hover:border-aether-primary/30 transition-all bg-transparent"
    @click="emit('create')"
  >
    <div class="w-12 h-12 rounded-full bg-aether-primary/10 flex items-center justify-center mb-4 group-hover:scale-110 group-hover:bg-aether-primary/20 transition-all">
      <i class="ra ra-plus text-xl text-aether-primary"></i>
    </div>
    <h3 class="text-xl font-bold text-white mb-2">Start New</h3>
    <p class="text-slate-500 text-sm max-w-[140px] text-center opacity-60">Begin your legend.</p>
  </button>
</template>
