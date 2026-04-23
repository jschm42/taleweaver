<script setup lang="ts">
const props = defineProps<{
  activeSection: 'templates' | 'sessions'
}>()

const emit = defineEmits<{
  (e: 'changeSection', section: 'templates' | 'sessions'): void
}>()
</script>

<template>
  <div class="flex items-end justify-between mb-12">
    <div>
      <h2 class="text-5xl font-black text-white font-display tracking-tight mb-3">My Library</h2>
      <p class="text-slate-500 font-narrative italic text-lg opacity-80">
        {{ props.activeSection === 'templates' ? 'Manage your world blueprints.' : 'Manage your active playthroughs.' }}
      </p>
    </div>
    <div class="flex bg-white/5 p-1 rounded-xl border border-white/5">
      <button
        class="px-4 py-1.5 rounded-lg text-xs font-bold transition-all"
        :class="props.activeSection === 'templates' ? 'bg-aether-primary/20 text-aether-primary' : 'text-slate-400 hover:text-white'"
        @click="emit('changeSection', 'templates')"
      >
        Adventures
      </button>
      <button
        class="px-4 py-1.5 rounded-lg text-xs font-bold transition-all"
        :class="props.activeSection === 'sessions' ? 'bg-aether-primary/20 text-aether-primary' : 'text-slate-400 hover:text-white'"
        @click="emit('changeSection', 'sessions')"
      >
        Sessions
      </button>
    </div>
  </div>
</template>
