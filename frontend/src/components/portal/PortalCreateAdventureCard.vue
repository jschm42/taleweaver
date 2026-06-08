<script setup lang="ts">
const emit = defineEmits<{
  (e: 'create'): void
}>()
</script>

<template>
  <article
    class="group flex flex-col border-2 border-dashed border-white/10 rounded-xl hover:border-amber-500/30 cursor-pointer transition-all bg-transparent overflow-hidden text-left h-full w-full"
    @click="emit('create')"
  >
    <!-- Placeholder Cover -->
    <div class="aspect-[3/2] w-full bg-white/5 flex items-center justify-center border-b border-dashed border-white/5">
       <div class="w-12 h-12 sm:w-16 sm:h-16 rounded-full bg-amber-500/10 border border-amber-400/20 flex items-center justify-center group-hover:scale-110 transition-transform">
        <img
          src="@/assets/svg/quill-feather-pen-with-ink-bottle.svg"
          alt="Start New Adventure"
          class="w-8 h-8 sm:w-10 sm:h-10 object-contain opacity-70 group-hover:opacity-100 transition-opacity"
        />
      </div>
    </div>

    <!-- Content Area -->
    <div class="p-4 sm:p-5 lg:p-6 lg:pt-5 flex flex-col gap-3 sm:gap-4 flex-1 w-full">
      <div class="space-y-2 flex-1">
        <h3 class="text-base sm:text-lg lg:text-xl font-black text-white leading-tight tracking-tight">Start New</h3>
        <div class="h-2 sm:h-4"></div>
        <p class="text-[11px] sm:text-xs font-bold text-slate-500 uppercase tracking-widest leading-relaxed">
          Begin your legend from scratch.
        </p>
      </div>

      <!-- Action Button -->
      <div
        class="w-full py-3 sm:py-3.5 rounded-xl text-[11px] sm:text-xs font-black uppercase tracking-widest transition-all border flex items-center justify-center gap-2 sm:gap-3 bg-amber-500/10 text-amber-400 border-amber-500/20 group-hover:bg-amber-500/20"
      >
        <i class="ra ra-quill-ink text-sm"></i>
        Start Editor
      </div>
    </div>
  </article>
</template>
