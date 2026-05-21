<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  open: boolean
  title: string
  unlockRule?: string | null
  items: any[]
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  takeAll: []
  dropToScene: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const hasItems = computed(() => (props.items || []).length > 0)

const onKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeyDown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[120] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-4xl bg-slate-900 border border-slate-700/60 rounded-3xl shadow-2xl overflow-hidden">
          <div class="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
            <div>
              <p class="text-[10px] uppercase tracking-[0.25em] text-emerald-400 font-black">Container</p>
              <h3 class="text-xl font-black text-white mt-1">{{ title }}</h3>
            </div>
            <button class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors" @click="emit('close')">
              <i class="ra ra-cancel"></i>
            </button>
          </div>

          <div v-if="unlockRule" class="mx-6 mt-5 px-4 py-3 rounded-xl border border-amber-400/25 bg-amber-400/10 text-amber-100 text-xs leading-relaxed">
            <span class="font-black uppercase tracking-widest text-amber-300 mr-2">Unlock Rule:</span>
            <span>{{ unlockRule }}</span>
          </div>

          <div class="p-6">
            <div v-if="hasItems" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 max-h-[46vh] overflow-y-auto custom-scrollbar pr-1">
              <div
                v-for="item in items"
                :key="item.id || item.name"
                class="bg-slate-950/50 border border-slate-800 rounded-2xl p-2 flex flex-col items-center gap-2"
                @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
                @mouseleave="emit('itemLeave')"
              >
                <div class="w-14 h-14 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center">
                  <img
                    v-if="item.image_url"
                    :src="getImageUrl(item.image_url)"
                    class="w-full h-full object-cover object-top"
                  />
                  <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/60">
                    <i :class="['ra text-xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                  </div>
                </div>
                <div class="w-full text-center">
                  <p class="text-[11px] font-bold text-slate-200 uppercase tracking-tight truncate">{{ item.name || item.id }}</p>
                  <p v-if="item.item_type" class="text-[9px] text-slate-500 uppercase tracking-widest mt-0.5">{{ item.item_type }}</p>
                </div>
              </div>
            </div>
            <div v-else class="h-40 rounded-2xl border border-slate-800 bg-slate-950/40 flex items-center justify-center text-slate-500 text-sm font-semibold uppercase tracking-wider">
              This container is empty.
            </div>
          </div>

          <div class="px-6 pb-6 pt-2 flex flex-wrap gap-3 justify-end border-t border-slate-800/80">
            <button
              class="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
              @click="emit('close')"
            >
              Close
            </button>
            <button
              class="px-4 py-2 rounded-xl border border-rose-500/30 text-rose-300 hover:text-white hover:bg-rose-600/30 transition-colors disabled:opacity-50"
              :disabled="busy || !hasItems"
              @click="emit('dropToScene')"
            >
              Drop To Scene
            </button>
            <button
              class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition-colors disabled:opacity-50"
              :disabled="busy || !hasItems"
              @click="emit('takeAll')"
            >
              Take All
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.custom-scrollbar::-webkit-scrollbar { width: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.35); border-radius: 9999px; }
</style>
