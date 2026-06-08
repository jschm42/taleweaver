<script setup lang="ts">
const emit = defineEmits<{
  (e: 'import'): void
}>()
</script>

<template>
  <article
    class="group flex flex-col border-2 border-dashed border-white/10 rounded-xl hover:border-blue-500/30 cursor-pointer transition-all bg-transparent overflow-hidden text-left h-full w-full"
    @click="emit('import')"
  >
    <!-- Placeholder Cover -->
    <div class="aspect-[3/2] w-full bg-white/5 flex items-center justify-center border-b border-dashed border-white/5">
       <div class="w-16 h-16 rounded-full bg-blue-500/10 border border-blue-400/20 flex items-center justify-center group-hover:scale-110 transition-transform">
        <img
          src="@/assets/svg/fantasy-spellbook.svg"
          alt="Import Example Adventures"
          class="w-10 h-10 object-contain opacity-70 group-hover:opacity-100 transition-opacity"
        />
      </div>
    </div>
    
    <!-- Content Area -->
    <div class="p-6 pt-5 flex flex-col gap-4 flex-1 w-full">
      <div class="space-y-2 flex-1">
        <h3 class="text-xl font-black text-white leading-tight tracking-tight">Import Examples</h3>
        <div class="h-4"></div>
        <p class="text-xs font-bold text-slate-500 uppercase tracking-widest leading-relaxed">
          Seed your library with classic tales.
        </p>
      </div>

      <!-- Action Button -->
      <div
        class="w-full py-3.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all border flex items-center justify-center gap-3 bg-blue-500/10 text-blue-400 border-blue-500/20 group-hover:bg-blue-500/20"
      >
        <i class="ra ra-book text-sm"></i>
        Import
      </div>
    </div>
  </article>
</template>
