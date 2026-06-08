<script setup lang="ts">
const emit = defineEmits<{
  (e: 'generate'): void
}>()
</script>

<template>
  <article
    class="group flex flex-col border-2 border-dashed border-white/10 rounded-xl hover:border-purple-500/30 cursor-pointer transition-all bg-transparent overflow-hidden text-left h-full w-full"
    @click="emit('generate')"
  >
    <!-- Placeholder Cover -->
    <div class="aspect-[3/2] w-full bg-white/5 flex items-center justify-center border-b border-dashed border-white/5">
       <div class="w-16 h-16 rounded-full bg-purple-500/10 border border-purple-400/20 flex items-center justify-center group-hover:scale-110 transition-transform">
        <img
          src="@/assets/svg/fantasy-rpg-map.svg"
          alt="Generate Adventure"
          class="w-10 h-10 object-contain opacity-70 group-hover:opacity-100 transition-opacity"
        />
      </div>
    </div>
    
    <!-- Content Area -->
    <div class="p-6 pt-5 flex flex-col gap-4 flex-1 w-full">
      <div class="space-y-2 flex-1">
        <h3 class="text-xl font-black text-white leading-tight tracking-tight">Generate Adventure</h3>
        <div class="h-4"></div>
        <p class="text-xs font-bold text-slate-500 uppercase tracking-widest leading-relaxed">
          Let the AI weave a custom sandbox world.
        </p>
      </div>

      <!-- Action Button -->
      <div
        class="w-full py-3.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border flex items-center justify-center gap-3 bg-purple-500/10 text-purple-400 border-purple-500/20 group-hover:bg-purple-500/20"
      >
        <i class="ra ra-crystal-ball text-sm"></i>
        Generate
      </div>
    </div>
  </article>
</template>
