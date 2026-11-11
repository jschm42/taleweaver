<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Eye, EyeOff, PackageCheck } from 'lucide-vue-next'
import type { InventoryItem } from '@/types'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'

const props = withDefaults(defineProps<{
  open: boolean
  items: InventoryItem[]
  evaluating?: boolean
}>(), {
  evaluating: false,
})

const emit = defineEmits<{
  take: [item: InventoryItem]
  leave: [item: InventoryItem]
  takeAll: []
  done: []
  entityHover: [entity: any, event: MouseEvent]
  entityLeave: []
}>()

const brokenImages = ref<Record<string, boolean>>({})
const isMinimized = ref(false)

watch(() => props.open, (isOpen) => {
  emit('entityLeave')
  if (isOpen) {
    isMinimized.value = false
  }
})

function itemKey(item: InventoryItem): string {
  return String(item.id || item.name || 'loot-item')
}

function onItemImageError(item: InventoryItem): void {
  brokenImages.value[itemKey(item)] = true
}

function canShowImage(item: InventoryItem): boolean {
  return hasRenderableImagePath(item.image_url) && !brokenImages.value[itemKey(item)]
}

function onHover(item: InventoryItem, event: MouseEvent): void {
  emit('entityHover', {
    ...item,
    entity_type: 'ITEM',
    type: 'ITEM',
    description: item.description || 'Loot recovered from battle.',
  }, event)
}

function handleTake(item: InventoryItem): void {
  emit('entityLeave')
  emit('take', item)
}

function handleLeave(item: InventoryItem): void {
  emit('entityLeave')
  emit('leave', item)
}

function handleTakeAll(): void {
  emit('entityLeave')
  emit('takeAll')
}

function handleDone(): void {
  emit('entityLeave')
  emit('done')
}

const itemCount = computed(() => props.items.length)
</script>

<template>
  <!-- Centered Loot Dialog Overlay -->
  <Transition name="tw-combat-loot">
    <div
      v-if="open && !isMinimized"
      class="tw-combat-loot-overlay absolute inset-0 z-40 flex items-center justify-center p-3 sm:p-6 bg-black/75 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      aria-label="Spoils of Battle"
    >
      <div class="tw-combat-panel tw-dialog relative w-full max-w-3xl flex flex-col max-h-[85vh] shadow-[0_20px_60px_rgba(0,0,0,0.85)] border border-amber-500/40 rounded-2xl overflow-hidden bg-slate-950/95">
        <!-- Dialog Header -->
        <header class="tw-combat-panel-header px-5 py-3.5 border-b flex items-center justify-between gap-3 shrink-0">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0 shadow-inner">
              <i class="ra ra-chest text-xl"></i>
            </div>
            <div class="min-w-0">
              <div class="tw-combat-eyebrow text-amber-400/90 leading-none mb-1">Victory Spoils</div>
              <h3 class="text-base sm:text-lg font-black text-amber-100 flex items-center gap-2 truncate">
                Spoils of Battle
                <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  {{ itemCount }} {{ itemCount === 1 ? 'item' : 'items' }}
                </span>
              </h3>
            </div>
          </div>
          <button
            type="button"
            class="tw-dialog-icon-button tw-combat-toggle w-8 h-8 text-slate-400 hover:text-amber-200"
            title="Minimize to inspect arena & battle log"
            @click="isMinimized = true; emit('entityLeave')"
          >
            <EyeOff class="w-4 h-4" />
          </button>
        </header>

        <!-- Dialog Content -->
        <div class="p-4 sm:p-5 flex-1 min-h-0 flex flex-col">
          <p class="text-xs sm:text-sm text-slate-300/80 mb-3 shrink-0">
            {{ itemCount > 0
              ? 'Click any item to take it into your inventory, or use the buttons below.'
              : 'All spoils have been claimed. You can return to your adventure.' }}
          </p>

          <!-- Tile Grid (Container style) -->
          <div
            v-if="itemCount > 0"
            class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 max-h-[48vh] overflow-y-auto p-1 custom-scrollbar"
          >
            <div
              v-for="item in items"
              :key="itemKey(item)"
              role="button"
              tabindex="0"
              class="tw-prompt-tile group relative aspect-square flex items-center justify-center overflow-hidden border border-amber-500/30 hover:border-amber-400 bg-black/40 hover:bg-amber-500/10 rounded-xl transition-all cursor-pointer shadow-md hover:shadow-[0_0_15px_rgba(245,158,11,0.25)]"
              :class="{ 'opacity-50 pointer-events-none': evaluating }"
              :title="`Click to take ${item.name || item.id}`"
              @click="handleTake(item)"
              @keydown.enter.prevent="handleTake(item)"
              @keydown.space.prevent="handleTake(item)"
              @mouseenter="onHover(item, $event)"
              @mousemove="onHover(item, $event)"
              @mouseleave="emit('entityLeave')"
            >
              <img
                v-if="canShowImage(item)"
                :src="getImageUrl(item.image_url)"
                class="w-full h-full object-cover object-top transition-transform duration-200 group-hover:scale-105"
                :alt="item.name || 'loot item'"
                @error="onItemImageError(item)"
              />
              <i
                v-else
                :class="['ra text-3xl sm:text-4xl transition-transform duration-200 group-hover:scale-110', getItemIcon(item.item_type), getTypeColor(item.item_type)]"
              ></i>

              <span class="tw-prompt-tile-caption">{{ item.name || item.id }}</span>

              <!-- Drop button on tile hover -->
              <button
                type="button"
                class="absolute top-1.5 right-1.5 z-10 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-black/80 hover:bg-rose-900/90 text-rose-300 border border-rose-500/40 opacity-0 group-hover:opacity-100 transition-opacity shadow"
                title="Leave this item in the scene"
                :disabled="evaluating"
                @click.stop="handleLeave(item)"
              >
                Drop
              </button>
            </div>
          </div>

          <!-- Empty State -->
          <div v-else class="flex-1 flex flex-col items-center justify-center py-10 text-center text-slate-400">
            <PackageCheck class="w-12 h-12 mb-3 text-amber-400/70" />
            <div class="text-sm font-bold text-slate-200">No items remaining</div>
            <p class="text-xs text-slate-400 mt-1 max-w-sm">All spoils have been collected or left behind. Ready to conclude combat.</p>
          </div>
        </div>

        <!-- Dialog Footer -->
        <footer class="tw-combat-panel-header px-5 py-3 border-t flex flex-wrap items-center justify-between gap-3 shrink-0">
          <button
            type="button"
            class="tw-dialog-button tw-dialog-button--ghost !px-4 !py-2 text-xs sm:text-sm"
            :disabled="evaluating"
            :title="itemCount ? 'Leave remaining loot lying in the scene and finish' : 'End the fight'"
            @click="handleDone"
          >
            {{ itemCount ? 'Drop Rest & Finish' : 'Finish & Continue' }}
          </button>

          <button
            v-if="itemCount > 0"
            type="button"
            class="tw-dialog-button !bg-amber-600 hover:!bg-amber-500 !text-slate-950 font-black !px-6 !py-2 text-xs sm:text-sm flex items-center gap-2 shadow-lg"
            :disabled="evaluating"
            title="Put all remaining loot into your inventory and end the fight"
            @click="handleTakeAll"
          >
            <i class="ra ra-hand"></i> Take All &amp; Finish
          </button>
        </footer>
      </div>
    </div>
  </Transition>

  <!-- Minimized Banner -->
  <Transition name="fade">
    <div
      v-if="open && isMinimized"
      class="absolute bottom-4 right-4 z-30"
    >
      <button
        type="button"
        class="tw-dialog-button !bg-amber-600 hover:!bg-amber-500 !text-slate-950 font-black px-4 py-2 text-xs flex items-center gap-2 shadow-xl border border-amber-400"
        @click="isMinimized = false"
      >
        <Eye class="w-3.5 h-3.5" />
        <span>Open Spoils of Battle ({{ itemCount }})</span>
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.tw-combat-loot-enter-active,
.tw-combat-loot-leave-active {
  transition: opacity 0.25s ease;
}

.tw-combat-loot-enter-from,
.tw-combat-loot-leave-to {
  opacity: 0;
}

.tw-combat-loot-enter-active .tw-combat-panel,
.tw-combat-loot-leave-active .tw-combat-panel {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s ease;
}

.tw-combat-loot-enter-from .tw-combat-panel,
.tw-combat-loot-leave-to .tw-combat-panel {
  opacity: 0;
  transform: scale(0.95) translateY(8px);
}
</style>

