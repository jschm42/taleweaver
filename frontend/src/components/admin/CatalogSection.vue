<script setup lang="ts">
import type { CatalogTile } from '@/types'

const props = defineProps<{
  type: 'styles' | 'tones'
  catalog: CatalogTile[]
  isGeneratingItem: Record<string, boolean>
  openMenuId: string | null
  simpleModel: string
}>()

const emit = defineEmits<{
  (e: 'addItem'): void
  (e: 'editItem', payload: { item: CatalogTile, index: number }): void
  (e: 'removeItem', index: number): void
  (e: 'generateImage', payload: { item: CatalogTile, index: number }): void
  (e: 'openPrompt', payload: { item: CatalogTile, index: number }): void
  (e: 'uploadImage', payload: { event: Event, item: CatalogTile, index: number }): void
  (e: 'updateMenuId', id: string | null): void
}>()

function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

const triggerFileUpload = (index: number) => {
  const input = document.getElementById(`${props.type}-upload-${index}`) as HTMLInputElement
  input?.click()
}

const isItemGenerating = (index: number): boolean => {
  return props.isGeneratingItem[`${props.type}_${index}`] ?? false
}
</script>

<template>
  <div class="space-y-8 animate-fade-in pb-16">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-4xl font-extrabold text-white mb-2">
          {{ type === 'styles' ? 'Image Style Catalog' : 'World Tone Catalog' }}
        </h1>
        <p class="text-slate-400 text-sm">
          {{ type === 'styles' ? 'Define selectable visual styles used during adventure image generation.' : 'Define selectable tone presets used for story/world generation.' }}
        </p>
      </div>
      <button 
        @click="emit('addItem')" 
        :class="['px-6 py-3 text-white font-bold rounded-xl shadow-lg flex items-center gap-2 transition-all', type === 'styles' ? 'bg-amber-600 hover:bg-amber-500 shadow-amber-900/20' : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-900/20']"
      >
        <i class="ra ra-plus"></i> Add {{ type === 'styles' ? 'Style' : 'Tone' }}
      </button>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3.5">
      <div
        v-for="(item, index) in catalog"
        :key="item.id + '-' + index"
        :class="[
          'group relative bg-slate-900 border border-slate-800 rounded-xl transition-all shadow-md',
          openMenuId === type + '-' + index ? 'z-30' : 'z-0',
          type === 'styles' ? 'hover:border-amber-500/50' : 'hover:border-indigo-500/50'
        ]"
      >
        <!-- Image Section -->
        <div class="relative aspect-[16/10] bg-slate-950 overflow-hidden rounded-t-xl">
          <img v-if="item.image_url" :src="item.image_url" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
          <div v-else class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 to-slate-950 text-slate-700">
            <svg v-if="type === 'styles'" class="w-8 h-8 opacity-30 mb-1 animate-pulse-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" />
              <path d="M12 8v4l3 3" />
              <path d="M9 3v2" /><path d="M5 5L6.5 6.5" /><path d="M3 9h2" /><path d="M3 15h2" /><path d="M5 19l1.5-1.5" /><path d="M9 21v-2" /><path d="M15 21v-2" /><path d="M19 19l-1.5-1.5" /><path d="M21 15h-2" /><path d="M21 9h-2" /><path d="M19 5L17.5 6.5" /><path d="M15 3v2" />
            </svg>
            <svg v-else class="w-8 h-8 opacity-30 mb-1 animate-pulse-slow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            <span class="text-[9px] uppercase tracking-widest font-bold opacity-30">No {{ type === 'styles' ? 'Style' : 'Tone' }} Image</span>
          </div>

          <!-- Hidden Upload Input -->
          <input
            :id="type + '-upload-' + index"
            type="file"
            class="hidden"
            accept="image/*"
            @change="(e) => emit('uploadImage', { event: e, item, index })"
          />

          <!-- Loading Overlay -->
          <div v-if="isItemGenerating(index)" class="absolute inset-0 bg-black/60 flex items-center justify-center">
            <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500"></div>
          </div>
        </div>

        <!-- Content Section -->
        <div class="p-3">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <h3 class="text-xs font-bold text-white truncate">{{ item.name }}</h3>
              <p class="text-slate-500 text-[10px] uppercase font-mono truncate">{{ item.id }}</p>
            </div>
            <div class="relative">
              <button
                type="button"
                @click.stop="emit('updateMenuId', openMenuId === type + '-' + index ? null : type + '-' + index)"
                class="w-6 h-6 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition-colors text-sm font-bold flex items-center justify-center cursor-pointer"
                title="Options"
              >
                <span>…</span>
              </button>

              <div
                v-if="openMenuId === type + '-' + index"
                class="fixed inset-0 z-[90]"
                @click="emit('updateMenuId', null)"
              ></div>

              <div
                v-if="openMenuId === type + '-' + index"
                class="absolute right-0 top-full mt-1.5 w-44 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl z-[100] py-1.5 overflow-hidden animate-fade-in ring-1 ring-white/10"
              >
                <button
                  type="button"
                  @click="emit('generateImage', { item, index }); emit('updateMenuId', null)"
                  :disabled="isItemGenerating(index)"
                  class="group/btn w-full text-left px-3.5 py-2 text-xs font-bold text-slate-300 hover:bg-emerald-600 hover:text-white flex items-center gap-2.5 transition-colors disabled:opacity-50 cursor-pointer"
                  :title="'Quick Generate using ' + simpleModel"
                >
                  <i :class="['ra ra-cycle text-emerald-400 group-hover/btn:text-white shrink-0 text-xs', isItemGenerating(index) ? 'animate-spin' : '']"></i>
                  <span class="truncate">Quick Generate</span>
                </button>

                <button
                  type="button"
                  @click="emit('openPrompt', { item, index }); emit('updateMenuId', null)"
                  class="group/btn w-full text-left px-3.5 py-2 text-xs font-bold text-slate-300 hover:bg-cyan-600 hover:text-white flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <i class="ra ra-quill-ink text-cyan-400 group-hover/btn:text-white shrink-0 text-xs"></i>
                  <span class="truncate">Custom Prompt</span>
                </button>

                <button
                  type="button"
                  @click="triggerFileUpload(index); emit('updateMenuId', null)"
                  class="group/btn w-full text-left px-3.5 py-2 text-xs font-bold text-slate-300 hover:bg-amber-600 hover:text-white flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <i class="ra ra-camera text-amber-400 group-hover/btn:text-white shrink-0 text-xs"></i>
                  <span class="truncate">Upload Image</span>
                </button>

                <button
                  type="button"
                  @click="emit('editItem', { item, index }); emit('updateMenuId', null)"
                  class="group/btn w-full text-left px-3.5 py-2 text-xs font-bold text-slate-300 hover:bg-blue-600 hover:text-white flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <i class="ra ra-quill text-blue-400 group-hover/btn:text-white shrink-0 text-xs"></i>
                  <span class="truncate">Edit</span>
                </button>

                <div class="h-px bg-slate-700/60 my-1"></div>

                <button
                  type="button"
                  @click="emit('removeItem', index); emit('updateMenuId', null)"
                  class="group/btn w-full text-left px-3.5 py-2 text-xs font-bold text-red-400 hover:bg-red-600 hover:text-white flex items-center gap-2.5 transition-colors cursor-pointer"
                >
                  <i class="ra ra-burning-embers text-red-400 group-hover/btn:text-white shrink-0 text-xs"></i>
                  <span class="truncate">Delete</span>
                </button>
              </div>
            </div>
          </div>
          <p class="text-slate-400 text-[11px] mt-1.5 line-clamp-2 min-h-[2.4em] leading-snug whitespace-pre-wrap">{{ fixNewlines(item.description) || 'No description provided.' }}</p>
        </div>
      </div>
      
      <div v-if="catalog.length === 0" class="col-span-full py-20 text-center border-2 border-dashed border-slate-800 rounded-3xl text-slate-600 italic">
        No {{ type }} in catalog yet. Click "Add {{ type === 'styles' ? 'Style' : 'Tone' }}" to begin.
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-pulse-slow {
  animation: pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.1; }
}
</style>
