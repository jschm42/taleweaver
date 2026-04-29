<script setup lang="ts">
const props = defineProps<{
  activeSection: 'templates' | 'sessions'
}>()

const emit = defineEmits<{
  (e: 'changeSection', section: 'templates' | 'sessions'): void
  (e: 'create'): void
  (e: 'import'): void
}>()
</script>

<template>
  <div class="flex items-end justify-between mb-12">
    <div>
      <h2 class="text-5xl font-black text-white font-display tracking-tight mb-2">
        {{ props.activeSection === 'templates' ? 'Library' : 'Game sessions' }}
      </h2>
      <p class="text-slate-500 font-narrative italic text-lg opacity-80">
        {{ props.activeSection === 'templates' ? 'Manage your world blueprints.' : 'Manage your active playthroughs.' }}
      </p>
    </div>
    <div class="flex items-center gap-3">
      <div v-if="props.activeSection === 'templates'" class="flex gap-2">
        <button
          class="px-4 py-2 rounded-xl bg-aether-primary/10 border border-aether-primary/20 text-aether-primary text-xs font-bold uppercase tracking-widest hover:bg-aether-primary/20 transition-all flex items-center gap-2"
          @click="emit('create')"
        >
          <i class="ra ra-scroll"></i>
          Generate adventure...
        </button>
        <button
          class="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300 text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all flex items-center gap-2"
          @click="emit('import')"
        >
          <i class="ra ra-download"></i>
          Import Adventure
        </button>
      </div>
    </div>
  </div>
</template>
