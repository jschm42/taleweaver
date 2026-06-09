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
  <div class="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl md:rounded-3xl p-4 sm:p-5 md:p-8 flex flex-col min-h-0">
    <div class="flex items-start justify-between gap-3 sm:gap-4 mb-4 sm:mb-6 md:mb-8">
      <div class="flex items-center gap-3 sm:gap-4 min-w-0">
        <div :class="['w-10 h-10 sm:w-11 sm:h-11 md:w-12 md:h-12 rounded-2xl flex items-center justify-center shrink-0', accentColorClass]">
          <component :is="icon" class="w-5 h-5 sm:w-5 sm:h-5 md:w-6 md:h-6" />
        </div>
        <div class="min-w-0">
          <h3 class="text-xs sm:text-sm font-black text-white uppercase tracking-[0.2em] truncate">{{ title }}</h3>
          <p class="text-xxs text-white/40 uppercase tracking-widest truncate">{{ subtitle }}</p>
        </div>
      </div>
      <InfoPopoverButton v-if="helpText" :title="title" :text="helpText" />
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 overflow-y-auto pr-1 sm:pr-2 custom-scrollbar max-h-[60vh] sm:max-h-[416px]">
      <button
        v-for="item in items"
        :key="item.id"
        @click="emit('select', item.id)"
        class="relative h-28 sm:h-32 rounded-2xl overflow-hidden border-2 sm:border-4 transition-all duration-300 group"
        :class="selectedId === item.id ? 'border-blue-500 ring-4 sm:ring-8 ring-blue-500/10' : 'border-transparent hover:border-white/10'"
      >
        <img :src="item.image_url ?? ''" class="w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-110" />
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
        <div class="absolute bottom-3 left-3 right-3 sm:bottom-4 sm:left-4 sm:right-4 text-left">
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
