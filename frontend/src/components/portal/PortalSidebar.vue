<script setup lang="ts">
const props = defineProps<{
  isAdmin: boolean
}>()

const emit = defineEmits<{
  (e: 'import'): void
  (e: 'create'): void
  (e: 'admin'): void
  (e: 'profile'): void
}>()
</script>

<template>
  <aside class="w-72 bg-aether-background/95 backdrop-blur-2xl border-r border-white/5 flex flex-col z-50 overflow-y-auto">
    <div class="p-8 pb-4">
      <nav class="space-y-1">
        <button class="w-full flex items-center gap-4 px-4 py-3 rounded-xl bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary transition-all">
          <span class="text-sm font-bold tracking-wide">My Library</span>
        </button>
        <button class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all">
          <span class="text-sm font-bold tracking-wide">Community Stories</span>
        </button>
        <button @click="emit('import')" class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all">
          <span class="text-sm font-bold tracking-wide">Import .adv / .adz</span>
        </button>
        <button @click="emit('profile')" class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all">
          <span class="text-sm font-bold tracking-wide">Profile</span>
        </button>
        <button
          v-if="props.isAdmin"
          @click="emit('admin')"
          class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all"
        >
          <span class="text-sm font-bold tracking-wide">Administration</span>
        </button>
      </nav>
    </div>

    <div class="mt-auto p-8">
      <button @click="emit('create')" class="btn-primary w-full flex items-center justify-center gap-3 !py-4 shadow-ambient-emerald/20">
        <i class="ra ra-plus"></i>
        Start New Adventure
      </button>
    </div>
  </aside>
</template>
