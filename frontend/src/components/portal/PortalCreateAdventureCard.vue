<script setup lang="ts">
const emit = defineEmits<{
  (e: 'create'): void
}>()
</script>

<template>
  <button
    class="group flex flex-col border-2 border-dashed border-white/10 rounded-xl hover:border-aether-primary/30 transition-all bg-transparent overflow-hidden text-left h-full"
    @click="emit('create')"
  >
    <!-- Placeholder Cover -->
    <div class="aspect-[3/2] w-full bg-white/5 flex items-center justify-center border-b border-dashed border-white/5">
       <div class="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-400/20 flex items-center justify-center group-hover:scale-110 transition-transform">
        <img
          src="@/assets/svg/quill-feather-pen-with-ink-bottle.svg"
          alt="Start New Adventure"
          class="w-10 h-10 object-contain opacity-70 group-hover:opacity-100 transition-opacity"
        />
      </div>
    </div>
    
    <div class="p-6 flex flex-col gap-2">
      <h3 class="text-2xl font-black text-white leading-tight tracking-tight">Start New</h3>
      <p class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Begin your legend from scratch.</p>
    </div>
  </button>
</template>
