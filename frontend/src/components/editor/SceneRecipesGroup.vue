<script setup lang="ts">
import { Brain } from 'lucide-vue-next'
import { getItemIcon, getTypeColor } from '@/utils/game_icons'

/**
 * Recipes group of the scene view. CONSTRUCTABLE recipes are meta items that never appear in the
 * world, so they have no image and their menu offers no image actions and no "Move to Scene".
 */
const props = defineProps<{
  recipes: any[]
  total: number
  activeMenuId: string | null
  hasScript: (obj: any) => boolean
}>()

const emit = defineEmits<{
  (e: 'create'): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'clone', id: string): void
  (e: 'edit', obj: any): void
  (e: 'delete', id: string): void
}>()

const menuId = (obj: any) => `scene-recipe-${obj.id}`
const menuItemClass = 'w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:text-white transition-all'
</script>

<template>
  <div class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
    <div class="flex items-center justify-between mb-2">
      <p class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Recipes ({{ recipes.length }}/{{ total }})</p>
      <div class="flex items-center gap-4">
        <span class="text-[10px] text-slate-500 uppercase tracking-widest">Never in the world · no image</span>
        <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('create')">+ Create</button>
      </div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
      <article
        v-for="obj in recipes"
        :key="obj.id"
        :class="[
          'relative group aspect-square bg-slate-900 border border-orange-500/20 rounded-xl shadow-lg overflow-visible',
          activeMenuId === menuId(obj) ? 'z-[180]' : 'z-0 hover:z-30',
        ]"
      >
        <div class="absolute inset-0 flex items-center justify-center pb-6">
          <i :class="['ra text-4xl opacity-70', getItemIcon('CONSTRUCTABLE'), getTypeColor('CONSTRUCTABLE')]"></i>
        </div>
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/25 to-transparent opacity-80"></div>
        <div class="absolute top-2 left-2 flex items-center gap-1 z-10">
          <div class="px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-orange-400/50 bg-orange-500/25 text-orange-100">RECIPE</div>
          <div
            v-if="props.hasScript(obj)"
            class="p-1 rounded-full border border-purple-500/50 bg-purple-950/80 text-purple-300 shadow-md flex items-center justify-center backdrop-blur-sm"
            title="Contains custom event script(s)"
          >
            <Brain class="w-3.5 h-3.5 text-purple-400" />
          </div>
        </div>
        <div class="absolute bottom-0 left-0 right-0 p-2">
          <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name || obj.id }}</div>
          <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
        </div>
        <div class="absolute top-2 right-2 z-40">
          <button
            @click="emit('toggle-menu', menuId(obj), $event)"
            class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg"
          >
            <div class="flex flex-col gap-0.5">
              <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
            </div>
          </button>
          <div v-if="activeMenuId === menuId(obj)" class="absolute right-0 mt-1 w-48 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
            <button @click="emit('clone', obj.id)" :class="[menuItemClass, 'hover:bg-sky-500']">Clone</button>
            <button @click="emit('edit', obj)" :class="[menuItemClass, 'hover:bg-blue-500']">Edit</button>
            <button @click="emit('delete', obj.id)" :class="[menuItemClass, 'hover:bg-red-500']">Delete</button>
          </div>
        </div>
      </article>
      <div v-if="recipes.length === 0" class="text-xs text-slate-500">No recipes match the current filter.</div>
    </div>
  </div>
</template>
