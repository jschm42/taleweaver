<script setup lang="ts">
import StatBar from '@/components/game/StatBar.vue'
import { getImageUrl, getItemIcon, hasRenderableImagePath } from '@/utils/game_icons'
import { fixNewlines, hasNonZero } from '@/services/hoverEntityService'

const props = defineProps<{
  hoveredEntity: any
  tooltipStyle: Record<string, string | number>
  tooltipImageFailed: boolean
  showsMechanics: boolean
  isConsumableHover: boolean
  ruleMode?: string | null
}>()

const emit = defineEmits<{
  (e: 'image-error'): void
}>()

const handleImageError = () => {
  emit('image-error')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="tooltip">
      <div
        v-if="props.hoveredEntity"
        class="fixed z-[999] pointer-events-none"
        :style="props.tooltipStyle"
      >
        <div class="w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl backdrop-blur-xl overflow-hidden flex flex-col animate-tooltip-in">
          <div v-if="hasRenderableImagePath(props.hoveredEntity.image_url) && !props.tooltipImageFailed" class="h-48 w-full relative">
            <img :src="getImageUrl(props.hoveredEntity.image_url)" class="absolute inset-0 w-full h-full object-cover object-top" @error="handleImageError" />
            <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
          </div>
          <div v-else class="h-32 w-full relative bg-slate-950 border-b border-slate-800 flex items-center justify-center">
            <i
              :class="[
                'ra text-4xl',
                props.hoveredEntity.entity_type?.toUpperCase() === 'NPC' ? 'ra-player text-cyan-400/80' : 'ra-vest text-amber-400/80'
              ]"
            ></i>
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(148,163,184,0.12),transparent_65%)]"></div>
          </div>

          <div class="p-4 bg-slate-900">
            <div class="flex items-center justify-between mb-1">
              <span class="text-sm font-bold text-white uppercase tracking-wider">{{ props.hoveredEntity.name }}</span>
              <span
                class="text-xxs px-1.5 py-0.5 rounded border font-mono uppercase"
                :class="props.hoveredEntity.entity_type?.toUpperCase() === 'NPC' ? 'border-cyan-500/50 text-cyan-400' : (props.hoveredEntity.entity_type?.toUpperCase() === 'SCENE' ? 'border-indigo-500/50 text-indigo-400' : 'border-amber-500/50 text-amber-400')"
              >
                {{ props.hoveredEntity.entity_type || 'OBJECT' }}
              </span>
            </div>
            <p class="text-xs text-slate-400 leading-relaxed italic mb-3 whitespace-pre-wrap">{{ fixNewlines(props.hoveredEntity.description) }}</p>

            <div v-if="props.hoveredEntity.entity_type?.toUpperCase() === 'NPC' && props.ruleMode !== 'chat'" class="flex flex-col gap-1 mt-3 pt-3 border-t border-slate-800">
              <StatBar v-if="props.hoveredEntity.hp != null" label="Health" :value="Number(props.hoveredEntity.hp)" :max="Number(props.hoveredEntity.max_hp || 100)" color="crimson" size="sm" />
              <StatBar v-if="props.hoveredEntity.stamina != null" label="Stamina" :value="Number(props.hoveredEntity.stamina)" :max="Number(props.hoveredEntity.max_stamina || 100)" color="emerald" size="sm" />
              <StatBar v-if="props.hoveredEntity.mana != null && props.ruleMode === 'rpg'" label="Mana" :value="Number(props.hoveredEntity.mana)" :max="Number(props.hoveredEntity.max_mana || 100)" color="sapphire" size="sm" />
            </div>

            <div v-if="props.hoveredEntity.entity_type?.toUpperCase() === 'NPC' && Array.isArray(props.hoveredEntity.inventory) && props.hoveredEntity.inventory.length > 0" class="mt-3 pt-3 border-t border-slate-800">
              <div class="flex items-center gap-1.5 mb-2">
                <i class="ra ra-treasure-chest text-xxs text-slate-500"></i>
                <span class="text-xxs font-black uppercase tracking-widest text-slate-500">Possessions</span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <div
                  v-for="(item, iidx) in props.hoveredEntity.inventory"
                  :key="item?.id || iidx"
                  class="px-2 py-1 rounded-lg bg-slate-950/60 border border-slate-800 text-xxs text-slate-300 flex items-center gap-1.5"
                >
                  <div v-if="typeof item === 'object' && item?.image_url" class="w-4 h-4 rounded overflow-hidden shrink-0 border border-slate-700">
                    <img :src="getImageUrl(item.image_url)" class="w-full h-full object-cover" />
                  </div>
                  <i v-else-if="typeof item === 'object'" :class="['ra text-[12px]', getItemIcon(item?.item_type || 'PICKABLE'), 'text-amber-500/60']"></i>
                  <i v-else class="ra ra-emerald text-[12px] text-amber-500/60"></i>
                  {{ typeof item === 'object' ? item?.name : item }}
                </div>
              </div>
            </div>

            <div v-if="(props.hoveredEntity.entity_type === 'OBJECT' || props.hoveredEntity.entity_type === 'ITEM') && props.ruleMode !== 'chat'" class="mt-3 pt-3 border-t border-slate-800">
              <div class="grid grid-cols-2 gap-2 text-xxs uppercase font-bold tracking-wider">
                <div v-if="props.hoveredEntity.slot" class="col-span-2 text-slate-500 lowercase italic font-medium">
                  {{ props.hoveredEntity.slot.replace('_', ' ') }}
                </div>

                <template v-if="props.isConsumableHover">
                  <div v-if="hasNonZero(props.hoveredEntity.hp_change)" class="text-red-400 flex justify-between">
                    <span>HP</span>
                    <span>{{ Number(props.hoveredEntity.hp_change) >= 0 ? '+' : '' }}{{ props.hoveredEntity.hp_change }}</span>
                  </div>
                  <div v-if="hasNonZero(props.hoveredEntity.mana_change)" class="text-blue-400 flex justify-between">
                    <span>Mana</span>
                    <span>{{ Number(props.hoveredEntity.mana_change) >= 0 ? '+' : '' }}{{ props.hoveredEntity.mana_change }}</span>
                  </div>
                  <div v-if="hasNonZero(props.hoveredEntity.stamina_change)" class="text-emerald-400 flex justify-between">
                    <span>Stamina</span>
                    <span>{{ Number(props.hoveredEntity.stamina_change) >= 0 ? '+' : '' }}{{ props.hoveredEntity.stamina_change }}</span>
                  </div>
                </template>

                <template v-if="props.showsMechanics">
                  <div v-if="hasNonZero(props.hoveredEntity.stat_modifier_strength)" class="text-red-400 flex justify-between">
                    <span>STR</span> <span>+{{ props.hoveredEntity.stat_modifier_strength }}</span>
                  </div>
                  <div v-if="hasNonZero(props.hoveredEntity.stat_modifier_dexterity)" class="text-emerald-400 flex justify-between">
                    <span>DEX</span> <span>+{{ props.hoveredEntity.stat_modifier_dexterity }}</span>
                  </div>
                  <div v-if="hasNonZero(props.hoveredEntity.stat_modifier_intelligence)" class="text-blue-400 flex justify-between">
                    <span>INT</span> <span>+{{ props.hoveredEntity.stat_modifier_intelligence }}</span>
                  </div>
                  <div v-if="hasNonZero(props.hoveredEntity.stat_modifier_wisdom)" class="text-purple-400 flex justify-between">
                    <span>WIS</span> <span>+{{ props.hoveredEntity.stat_modifier_wisdom }}</span>
                  </div>
                  <div v-if="hasNonZero(props.hoveredEntity.stat_modifier_charisma)" class="text-pink-400 flex justify-between">
                    <span>CHA</span> <span>+{{ props.hoveredEntity.stat_modifier_charisma }}</span>
                  </div>
                  <div v-if="hasNonZero(props.hoveredEntity.stat_modifier_armor_class)" class="text-amber-400 flex justify-between">
                    <span>AC</span> <span>+{{ props.hoveredEntity.stat_modifier_armor_class }}</span>
                  </div>
                </template>
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
</style>
