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
    <div class="w-20 h-20 mb-4 rounded-full bg-amber-500/20 border border-amber-400/40 flex items-center justify-center group-hover:scale-110 transition-transform">
      <img
        src="@/assets/svg/quill-feather-pen-with-ink-bottle.svg"
        alt="Start New Adventure"
        class="w-12 h-12 object-contain opacity-95"
      />
    </div>
    <h3 class="text-xl font-bold text-white mb-2">Start New</h3>
    <p class="text-slate-500 text-sm max-w-[140px] text-center opacity-60">Begin your legend.</p>
  </button>
</template>
