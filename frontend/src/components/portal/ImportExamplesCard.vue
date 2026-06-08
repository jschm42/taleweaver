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
    <div class="aspect-[4/3] sm:aspect-[3/2] w-full bg-white/5 flex items-center justify-center border-b border-dashed border-white/5">
       <div class="w-10 h-10 sm:w-16 sm:h-16 rounded-full bg-blue-500/10 border border-blue-400/20 flex items-center justify-center group-hover:scale-110 transition-transform">
        <img
          src="@/assets/svg/fantasy-spellbook.svg"
          alt="Import Example Adventures"
          class="w-7 h-7 sm:w-10 sm:h-10 object-contain opacity-70 group-hover:opacity-100 transition-opacity"
        />
      </div>
    </div>

    <!-- Content Area -->
    <div class="p-2.5 sm:p-5 lg:p-6 lg:pt-5 flex flex-col gap-2 sm:gap-4 flex-1 w-full">
      <div class="space-y-1 sm:space-y-2 flex-1">
        <h3 class="text-[11px] sm:text-lg lg:text-xl font-black text-white leading-tight tracking-tight">Import Examples</h3>
        <div class="hidden sm:block h-2 sm:h-4"></div>
        <p class="hidden sm:block text-[11px] sm:text-xs font-bold text-slate-500 uppercase tracking-widest leading-relaxed">
          Seed your library with classic tales.
        </p>
      </div>

      <!-- Action Button -->
      <div
        class="w-full py-2 sm:py-3.5 rounded-lg sm:rounded-xl text-[10px] sm:text-xs font-black uppercase tracking-widest transition-all border flex items-center justify-center gap-1.5 sm:gap-3 bg-blue-500/10 text-blue-400 border-blue-500/20 group-hover:bg-blue-500/20"
      >
        <i class="ra ra-book text-xs sm:text-sm"></i>
        Import
      </div>
    </div>
  </article>
</template>
