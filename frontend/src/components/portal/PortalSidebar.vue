<script setup lang="ts">
const props = defineProps<{
  isAdmin: boolean
  activeSection: 'templates' | 'sessions' | 'profile'
}>()

const emit = defineEmits<{
  (e: 'section', section: 'templates' | 'sessions' | 'profile'): void
  (e: 'admin'): void
}>()
</script>

<template>
  <aside class="w-72 bg-aether-background/95 backdrop-blur-2xl border-r border-white/5 flex flex-col z-50 overflow-y-auto">
    <div class="p-8 pb-4">
      <nav class="space-y-1">
        <button
          @click="emit('section', 'sessions')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl transition-all"
          :class="props.activeSection === 'sessions' ? 'bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
        >
          <span class="text-base font-bold tracking-wide">Sessions</span>
        </button>
        <button
          @click="emit('section', 'templates')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl transition-all"
          :class="props.activeSection === 'templates' ? 'bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
        >
          <span class="text-base font-bold tracking-wide">My Library</span>
        </button>
        <button
          @click="emit('section', 'profile')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl transition-all"
          :class="props.activeSection === 'profile' ? 'bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
        >
          <span class="text-base font-bold tracking-wide">Profile</span>
        </button>
        <button
          v-if="props.isAdmin"
          @click="emit('admin')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all"
        >
          <span class="text-base font-bold tracking-wide">Administration</span>
        </button>
      </nav>
    </div>
  </aside>
</template>
