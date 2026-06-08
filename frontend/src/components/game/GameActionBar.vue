<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  activeActionId?: string | null
  mode?: string
  disabled?: boolean
  suggestions?: string[]
}>()

const visibleSuggestions = computed(() => {
  const incoming = Array.isArray(props.suggestions) ? props.suggestions : []
  return incoming.filter(Boolean).slice(0, 3)
})

const emit = defineEmits<{
  selectAction: [actionId: string | null]
  useSuggestion: [suggestion: string]
  shuffleSuggestions: []
}>()
</script>

<template>
  <div class="flex items-center w-full p-2 bg-slate-900/80 border-t border-slate-800 backdrop-blur-md no-scrollbar shrink-0">
    <button
      :disabled="props.disabled"
      aria-label="Generate ideas"
      title="Generate ideas"
      class="ideas-trigger group flex items-center justify-center w-9 h-9 mr-2 border-r border-slate-800 rounded-lg transition-all duration-300 active:scale-95"
      :class="props.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'"
      @click="emit('shuffleSuggestions')"
    >
      <i class="ra ra-light-bulb text-amber-400 text-base transition-transform duration-300 group-hover:scale-110"></i>
    </button>

    <div class="flex items-center gap-2 overflow-x-auto no-scrollbar flex-grow">
      <button
        v-for="(suggestion, idx) in visibleSuggestions"
        :key="`${idx}-${suggestion}`"
        :disabled="props.disabled"
        :aria-label="`Use suggestion: ${suggestion}`"
        :title="suggestion"
        class="group relative flex items-center gap-2 px-3 py-1.5 rounded-full transition-all duration-300 active:scale-95 border text-xs font-semibold"
        :class="[
          props.disabled
            ? 'bg-slate-800/40 border-slate-700/50 opacity-40 cursor-not-allowed'
            : 'bg-slate-800/70 border-slate-700/70 text-slate-200 hover:bg-slate-700/70 hover:border-slate-500/70'
        ]"
        @click="emit('useSuggestion', suggestion)"
      >
        <span class="max-w-[22rem] truncate">{{ suggestion }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}

.ideas-trigger:not(:disabled):hover {
  background: rgba(251, 191, 36, 0.08);
  box-shadow: 0 0 16px -2px rgba(251, 191, 36, 0.55), inset 0 0 0 1px rgba(251, 191, 36, 0.2);
}
.ideas-trigger:not(:disabled):hover .ra-light-bulb {
  filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.8));
  color: rgb(252, 211, 77);
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(10px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
