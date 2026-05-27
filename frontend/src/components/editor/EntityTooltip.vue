<script setup lang="ts">
import { ref, watch } from 'vue'
import { getItemIcon, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  hoveredEntity: any | null
  activeMenuId: string | null
  mousePos: { x: number; y: number }
  tooltipAlignTop: boolean
  windowHeight: number
  ruleEnforcementMode: string
  buildVisualImageUrl: (path: string) => string
  fixNewlines: (text: string) => string
}>()

const tooltipImageSrc = ref('')
const tooltipImageFailed = ref(false)

watch(
  () => props.hoveredEntity?.image_url,
  (nextImagePath) => {
    tooltipImageFailed.value = false
    tooltipImageSrc.value = getImageUrl(nextImagePath, { thumbnail: true })
  },
  { immediate: true }
)

function onTooltipImageError() {
  if (tooltipImageSrc.value.includes('_thumb')) {
    const fallbackSrc = getOriginalImageUrl(props.hoveredEntity?.image_url)
    if (fallbackSrc && fallbackSrc !== tooltipImageSrc.value) {
      tooltipImageSrc.value = fallbackSrc
      return
    }
  }
  tooltipImageFailed.value = true
}
</script>

<template>
  <Teleport to="body">
    <Transition name="tooltip">
      <div 
        v-if="hoveredEntity && !activeMenuId" 
        class="fixed z-[100] pointer-events-none transition-opacity duration-75 flex flex-col"
        :style="{ 
          left: mousePos.x + 'px', 
          top: tooltipAlignTop ? 'auto' : (mousePos.y + 15) + 'px',
          bottom: tooltipAlignTop ? (windowHeight - mousePos.y + 15) + 'px' : 'auto'
        }"
      >
        <div class="w-64 max-h-[85vh] bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl backdrop-blur-xl overflow-y-auto flex flex-col animate-tooltip-in scrollbar-hide">
          <!-- Image Area -->
          <div v-if="hoveredEntity.image_url && !tooltipImageFailed" class="h-48 w-full relative">
            <img :src="tooltipImageSrc" @error="onTooltipImageError" class="absolute inset-0 w-full h-full object-cover object-center" />
            <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
          </div>

          <!-- Content -->
          <div class="p-4 bg-slate-900 space-y-3">
            <div class="flex items-start justify-between mb-1">
              <div class="flex flex-col">
                <span class="text-sm font-bold text-white uppercase tracking-wider leading-tight">{{ hoveredEntity.name }}</span>
                <span class="text-[10px] text-slate-500 font-mono uppercase tracking-tighter">{{ hoveredEntity.id }}</span>
              </div>
              <span 
                class="text-[9px] px-1.5 py-0.5 rounded border font-mono uppercase border-emerald-500/50 text-emerald-400 bg-emerald-500/5 shrink-0"
              >
                {{ hoveredEntity.type }}
              </span>
            </div>
            
            <!-- Stats Display (Mode Aware) -->
            <div v-if="ruleEnforcementMode !== 'chat' && hoveredEntity.stats" class="flex flex-wrap gap-2 pt-2 border-t border-white/5">
              <template v-if="hoveredEntity.type === 'NPC' || hoveredEntity.type === 'PROTAGONIST'">
                <div class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-xs font-black text-red-500">
                  <i class="ra ra-heart"></i> {{ hoveredEntity.stats.hp || 10 }}
                </div>
                <template v-if="ruleEnforcementMode === 'rpg' || ruleEnforcementMode === 'story'">
                  <div class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-xs font-black text-emerald-500">
                    <i class="ra ra-muscle-up"></i> {{ hoveredEntity.stats.stamina || 10 }}
                  </div>
                  <div v-if="ruleEnforcementMode === 'rpg'" class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-xs font-black text-blue-500">
                    <i class="ra ra-crystal-ball"></i> {{ hoveredEntity.stats.mana || 0 }}
                  </div>
                </template>
              </template>
              <template v-else-if="hoveredEntity.type === 'ITEM'">
                <div v-for="(val, stat) in hoveredEntity.stats" :key="stat" class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800 border border-white/10 text-xs font-bold text-slate-300 uppercase">
                  {{ String(stat).replace('_', ' ') }}: +{{ val }}
                </div>
              </template>
            </div>

            <p class="text-xs text-slate-400 leading-relaxed italic whitespace-pre-wrap">{{ fixNewlines(hoveredEntity.description) }}</p>

            <!-- NPC Inventory in Tooltip -->
            <div v-if="hoveredEntity.type === 'NPC' && hoveredEntity.inventory && hoveredEntity.inventory.length > 0" class="space-y-2 pt-2 border-t border-white/5">
              <div class="flex items-center gap-1.5">
                <i class="ra ra-treasure-chest text-[10px] text-slate-500"></i>
                <span class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Possessions</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <div v-for="item in hoveredEntity.inventory" :key="item.id" class="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-black/40 border border-white/5">
                  <div class="w-4 h-4 rounded-sm overflow-hidden shrink-0 border border-white/10">
                    <img v-if="item.image_url" :src="getImageUrl(item.image_url, { thumbnail: true })" class="w-full h-full object-cover" />
                    <div v-else class="w-full h-full flex items-center justify-center bg-slate-800">
                      <i :class="['ra text-[8px]', getItemIcon(item.item_type), 'text-slate-500']"></i>
                    </div>
                  </div>
                  <span class="text-[10px] font-bold text-slate-300 uppercase tracking-tight">{{ item.name }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.2s, transform 0.2s; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.95) translateY(5px); }

.animate-tooltip-in {
  animation: toolTipIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(10px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
