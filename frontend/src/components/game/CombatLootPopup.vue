<script setup lang="ts">
import { computed, ref } from 'vue'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'

type LootItem = {
  id?: string
  name?: string
  description?: string
  item_type?: string
}

const props = defineProps<{
  open: boolean
  items: LootItem[]
  busy?: boolean
}>()

const emit = defineEmits<{
  confirm: []
  close: []
  itemHover: [item: LootItem, event: MouseEvent]
  itemLeave: []
}>()

const brokenImages = ref<Record<string, boolean>>({})

function itemKey(item: LootItem): string {
  return String(item.id || item.name || 'unknown-item')
}

function onItemImageError(item: LootItem): void {
  brokenImages.value[itemKey(item)] = true
}

function canShowImage(item: LootItem): boolean {
  return hasRenderableImagePath(item.image_url) && !brokenImages.value[itemKey(item)]
}

const title = computed(() => {
  const count = props.items?.length || 0
  if (count <= 0) return 'Battle Resolved'
  if (count === 1) return 'Loot Recovered'
  return 'Loot Cache Recovered'
})
</script>

<template>
  <Teleport to="body">
    <Transition name="loot-popup-fade">
      <div v-if="open" class="fixed inset-0 z-[220] flex items-center justify-center px-4 py-8">
        <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" @click="emit('close')"></div>

        <section class="relative w-full max-w-2xl rounded-3xl border border-cyan-300/25 bg-gradient-to-b from-slate-900 via-slate-900/95 to-slate-950 shadow-[0_0_80px_rgba(34,211,238,0.22)] overflow-hidden">
          <div class="absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.22),transparent_72%)] pointer-events-none"></div>

          <header class="relative px-6 pt-6 pb-4 border-b border-slate-700/60">
            <div class="text-[11px] uppercase tracking-[0.24em] font-black text-cyan-200/80">Combat Reward</div>
            <h2 class="mt-2 text-2xl font-black tracking-tight text-white">{{ title }}</h2>
            <p class="mt-1 text-sm text-slate-300/90">
              {{ items.length > 0
                ? 'The defeated enemy dropped the following items.'
                : 'No useful loot was found.' }}
            </p>
          </header>

          <div class="relative px-6 py-5">
            <div v-if="items.length === 0" class="rounded-2xl border border-slate-700/70 bg-slate-950/70 px-4 py-6 text-center text-slate-300 text-sm">
              Nothing was left behind. You can close this combat now.
            </div>

            <div v-else class="space-y-2.5 max-h-[46vh] overflow-y-auto pr-1 custom-scrollbar">
              <article
                v-for="item in items"
                :key="item.id || item.name"
                class="rounded-xl border border-slate-700/80 bg-slate-950/60 px-3.5 py-3 flex items-start gap-3"
                @mouseenter="emit('itemHover', item, $event)"
                @mousemove="emit('itemHover', item, $event)"
                @mouseleave="emit('itemLeave')"
              >
                <div class="h-16 w-16 rounded-lg bg-slate-900 border border-slate-700/70 flex items-center justify-center shrink-0 overflow-hidden">
                  <img
                    v-if="canShowImage(item)"
                    :src="getImageUrl(item.image_url)"
                    class="w-full h-full object-cover"
                    :alt="item.name || 'loot item'"
                    @error="onItemImageError(item)"
                  >
                  <i v-else :class="['ra text-3xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
                </div>
                <div class="min-w-0">
                  <div class="text-sm font-bold text-slate-100 truncate">{{ item.name || 'Unknown Item' }}</div>
                  <div class="text-xs text-slate-400 leading-relaxed mt-1">{{ item.description || 'The item is within reach.' }}</div>
                </div>
              </article>
            </div>
          </div>

          <footer class="px-6 pb-6 pt-2 flex items-center justify-between gap-3">
            <button
              type="button"
              class="px-4 py-2.5 rounded-lg text-xs font-black uppercase tracking-[0.12em] border border-slate-600 text-slate-200 hover:border-slate-400 hover:text-white transition-colors"
              :disabled="busy"
              @click="emit('close')"
            >
              Manage In Combat Dialog
            </button>
            <button
              type="button"
              class="px-5 py-2.5 rounded-lg text-xs font-black uppercase tracking-[0.12em] bg-cyan-500/90 hover:bg-cyan-400 text-slate-950 shadow-[0_0_30px_rgba(34,211,238,0.45)] transition-all disabled:opacity-50"
              :disabled="busy"
              @click="emit('confirm')"
            >
              Drop Loot & Close Combat
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.loot-popup-fade-enter-active,
.loot-popup-fade-leave-active {
  transition: opacity 180ms ease;
}

.loot-popup-fade-enter-from,
.loot-popup-fade-leave-to {
  opacity: 0;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.6);
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.45);
  border-radius: 999px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.65);
}
</style>
