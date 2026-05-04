<script setup lang="ts">
const emit = defineEmits<{
  (e: 'import'): void
}>()
</script>

<template>
  <button
    class="group flex flex-col border-2 border-dashed border-white/10 rounded-xl hover:border-blue-500/30 transition-all bg-transparent overflow-hidden text-left h-full"
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
    
    <div class="p-6 flex flex-col gap-2">
      <h3 class="text-2xl font-black text-white leading-tight tracking-tight">Import Examples</h3>
      <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Seed your library with classic tales.</p>
    </div>
  </button>
</template>

