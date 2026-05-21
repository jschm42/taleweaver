<script setup lang="ts">
import type { CatalogTile } from '@/types'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'

defineProps<{
  title: string
  subtitle: string
  icon: any
  items: CatalogTile[]
  selectedId: string
  accentColorClass: string
  helpText?: string
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
}>()
</script>

<template>
  <div class="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-3xl p-8 flex flex-col min-h-0">
    <div class="flex items-start justify-between gap-4 mb-8">
      <div class="flex items-center gap-4">
        <div :class="['w-12 h-12 rounded-2xl flex items-center justify-center', accentColorClass]">
          <component :is="icon" class="w-6 h-6" />
        </div>
        <div>
          <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">{{ title }}</h3>
          <p class="text-xxs text-white/40 uppercase tracking-widest">{{ subtitle }}</p>
        </div>
      </div>
      <InfoPopoverButton v-if="helpText" :title="title" :text="helpText" />
    </div>

    <div class="grid grid-cols-2 gap-4 overflow-y-auto pr-2 custom-scrollbar max-h-[416px]">
      <button
        v-for="item in items"
        :key="item.id"
        @click="emit('select', item.id)"
        class="relative h-32 rounded-2xl overflow-hidden border-4 transition-all duration-300 group"
        :class="selectedId === item.id ? 'border-blue-500 ring-8 ring-blue-500/10' : 'border-transparent hover:border-white/10'"
      >
        <img :src="item.image_url ?? ''" class="w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-110" />
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
        <div class="absolute bottom-4 left-4 right-4 text-left">
          <p class="text-xxs font-black text-white uppercase tracking-widest">{{ item.name }}</p>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.25);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.45);
}
</style>
