<script setup lang="ts">
import { computed, ref } from 'vue'
import { visualService } from '@/services/visualService'

interface ExistingItem {
  id: string
  name?: string
  label?: string
  description?: string
  item_type?: string
  current_scene_id?: string
  image_url?: string | null
}

const props = defineProps<{
  show: boolean
  kind: 'items' | 'switch' | 'container' | 'text-log' | 'npc'
  sceneLabel?: string
  items: ExistingItem[]
  visualsCacheVersion?: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', itemId: string): void
}>()

const searchQuery = ref('')

const kindMeta = computed(() => {
  switch (props.kind) {
    case 'switch':
      return { label: 'Switch', icon: 'ra-lightning-bolt', color: 'text-lime-300' }
    case 'container':
      return { label: 'Container', icon: 'ra-chest', color: 'text-amber-300' }
    case 'text-log':
      return { label: 'Text Log', icon: 'ra-scroll-unfurled', color: 'text-cyan-300' }
    case 'npc':
      return { label: 'NPC', icon: 'ra-player', color: 'text-sky-300' }
    case 'items':
    default:
      return { label: 'Item', icon: 'ra-key', color: 'text-slate-200' }
  }
})

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.items
  return props.items.filter((entry) => {
    const haystack = [entry.id, entry.name, entry.label, entry.description, entry.item_type, entry.current_scene_id]
      .map((value: any) => String(value || '').toLowerCase())
      .join(' ')
    return haystack.includes(q)
  })
})

function handleSelect(itemId: string) {
  emit('select', itemId)
}

function itemSubtitle(entry: ExistingItem): string {
  const parts: string[] = []
  if (entry.item_type) parts.push(String(entry.item_type).toUpperCase())
  if (entry.current_scene_id) parts.push(`from ${entry.current_scene_id}`)
  return parts.join(' • ')
}

function itemSubtitleForKind(entry: ExistingItem, kind: 'items' | 'switch' | 'container' | 'text-log' | 'npc'): string {
  if (kind === 'npc') {
    return entry.current_scene_id ? `from ${entry.current_scene_id}` : 'No scene assigned'
  }
  return itemSubtitle(entry)
}

function buildImageUrl(imagePath: string | null | undefined): string {
  return visualService.buildImageUrl(imagePath, props.visualsCacheVersion ?? 0)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60" @click.self="emit('close')">
        <div class="modal-content w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2rem] shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
          <div class="p-6 pb-4 border-b border-white/5">
            <div class="flex justify-between items-center mb-4">
              <div class="space-y-1">
                <h3 class="text-xs font-black text-amber-400 uppercase tracking-widest">Add Existing {{ kindMeta.label }}</h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">
                  Scene: {{ sceneLabel || 'Current Scene' }}
                </p>
              </div>
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>
            <div class="relative">
              <i class="ra ra-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
              <input
                v-model="searchQuery"
                class="w-full bg-black/40 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:border-amber-500/50 outline-none transition-all"
                placeholder="Search by id, name, description, type, current scene..."
              />
            </div>
          </div>

          <div class="p-6 overflow-y-auto">
            <div v-if="items.length === 0" class="text-center py-10 text-slate-500 text-sm space-y-2">
              <i class="ra ra-scroll-quill text-2xl text-slate-600"></i>
              <p>No existing {{ kindMeta.label.toLowerCase }}s available in this adventure.</p>
              <p class="text-[11px] text-slate-600">Items currently placed in this scene are not listed here.</p>
            </div>
            <div v-else-if="filteredItems.length === 0" class="text-center py-8 text-slate-500 text-sm">
              No matches for your search.
            </div>
            <div v-else class="space-y-2">
              <button
                v-for="entry in filteredItems"
                :key="entry.id"
                class="group w-full flex items-center gap-3 p-3 rounded-xl border border-white/10 bg-slate-950/40 text-left transition-all duration-200 hover:bg-slate-800/60 hover:border-amber-500/30 hover:shadow-lg hover:shadow-amber-900/10"
                @click="handleSelect(entry.id)"
              >
                <div class="flex items-center justify-center w-12 h-12 rounded-lg bg-slate-900 border border-white/10 shrink-0 group-hover:border-amber-500/30 overflow-hidden">
                  <img
                    v-if="entry.image_url"
                    :src="buildImageUrl(entry.image_url)"
                    :alt="entry.name || entry.label || entry.id"
                    class="w-full h-full object-cover"
                  />
                  <i v-else :class="[kindMeta.icon, kindMeta.color, 'text-lg']"></i>
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2 mb-0.5">
                    <span class="text-xs font-black text-white uppercase tracking-wider truncate">{{ entry.name || entry.label || entry.id }}</span>
                    <span class="text-[9px] font-mono text-slate-600 uppercase tracking-wider shrink-0">{{ entry.id }}</span>
                  </div>
                  <p class="text-[11px] text-slate-400 truncate">{{ itemSubtitleForKind(entry, props.kind) || 'No additional details' }}</p>
                </div>
                <i class="ra ra-arrow-right text-slate-500 group-hover:text-amber-300 transition-colors"></i>
              </button>
            </div>
          </div>

          <div class="p-4 border-t border-white/5 flex justify-end">
            <button
              @click="emit('close')"
              class="px-6 py-2.5 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-content {
  animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-leave-active .modal-content {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform: scale(0.95);
}
@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.9) translateY(40px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
