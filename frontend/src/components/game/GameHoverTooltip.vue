<script setup lang="ts">
import { computed } from 'vue'
import StatBar from '@/components/game/StatBar.vue'
import { getImageUrl, getItemIcon, hasRenderableImagePath } from '@/utils/game_icons'
import { fixNewlines, hasNonZero } from '@/services/hoverEntityService'
import { formatObjectIds } from '@/utils/editor_utils'

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

const hasHeroImage = computed(() =>
  hasRenderableImagePath(props.hoveredEntity?.image_url) && !props.tooltipImageFailed,
)

const hasObjectDetails = computed(() => {
  const entity = props.hoveredEntity
  if (!entity) return false
  if (entity.slot) return true

  if (props.isConsumableHover) {
    if (hasNonZero(entity.hp_change)) return true
    if (hasNonZero(entity.mana_change)) return true
    if (hasNonZero(entity.stamina_change)) return true
  }

  if (props.showsMechanics) {
    if (hasNonZero(entity.stat_modifier_strength)) return true
    if (hasNonZero(entity.stat_modifier_dexterity)) return true
    if (hasNonZero(entity.stat_modifier_intelligence)) return true
    if (hasNonZero(entity.stat_modifier_wisdom)) return true
    if (hasNonZero(entity.stat_modifier_charisma)) return true
    if (hasNonZero(entity.stat_modifier_armor_class)) return true
  }

  return false
})

const entityTypeUpper = computed(() =>
  String(props.hoveredEntity?.entity_type || '').toUpperCase()
)
const isExit = computed(() => entityTypeUpper.value === 'EXIT')
const isNpc = computed(() => entityTypeUpper.value === 'NPC')
const isScene = computed(() => entityTypeUpper.value === 'SCENE')

const headerPaddingClass = computed(() => isExit.value ? 'px-3 pt-2' : 'p-3.5')
const bodyPaddingClass = computed(() => isExit.value ? 'px-3 pb-2' : 'px-3.5')
const detailsPaddingClass = computed(() => isExit.value ? 'px-3 pb-2' : 'mt-1 px-3.5 pb-3.5')
const headerLabelClass = computed(() => isExit.value ? 'text-[11px]' : 'text-sm')
const bodyTextClass = computed(() => isExit.value ? 'text-[13px] mb-2' : 'text-xs mb-2')

const badgeBorderClass = computed(() => {
  if (isScene.value) return 'border-indigo-500/50 text-indigo-400'
  if (isExit.value) return 'border-cyan-500/50 text-cyan-300'
  return 'border-amber-500/50 text-amber-400'
})

const entityTypeLabel = computed(() => props.hoveredEntity?.entity_type || 'OBJECT')
const entityName = computed(() => props.hoveredEntity?.name || '')
const entityDescription = computed(() => props.hoveredEntity?.description || '')
const isEntityLocked = computed(() => !!props.hoveredEntity?.is_locked)
</script>

<template>
  <Teleport to="body">
    <Transition name="tooltip">
      <div
        v-if="props.hoveredEntity"
        class="fixed z-[999] pointer-events-none"
        :style="props.tooltipStyle"
      >
        <div
          class="w-full max-w-full bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl backdrop-blur-xl overflow-hidden flex flex-col animate-tooltip-in"
          :class="props.hoveredEntity.entity_type?.toUpperCase() === 'NPC' ? 'min-h-[26rem]' : 'min-h-[20rem]'"
        >

          <!-- Image (NPC only) -->
          <div v-if="hasHeroImage" class="h-72 w-full relative shrink-0">
            <div
              v-if="props.hoveredEntity.entity_type?.toUpperCase() === 'NPC' && (props.hoveredEntity.is_defeated || props.hoveredEntity.hp === 0)"
              class="absolute -right-8 top-3 bg-red-600 text-white text-[10px] font-black uppercase tracking-[0.12em] py-1 w-28 text-center rotate-45 shadow-lg z-20"
            >
              Defeated
            </div>
            <img :src="getImageUrl(props.hoveredEntity.image_url)" class="absolute inset-0 w-full h-full object-cover object-top" @error="handleImageError" />
            <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/20 to-transparent"></div>
             <div class="tooltip-image-fray absolute left-0 right-0 bottom-0 h-12"></div>
          </div>
          <div v-else :class="['w-full relative bg-slate-950 flex items-center justify-center shrink-0', isExit ? 'h-16' : 'h-20']">
            <div
              v-if="isNpc && (props.hoveredEntity.is_defeated || props.hoveredEntity.hp === 0)"
              class="absolute -right-8 top-2 bg-red-600 text-white text-[9px] font-black uppercase tracking-[0.12em] py-0.5 w-24 text-center rotate-45 shadow-lg z-20"
            >
              Defeated
            </div>
            <i
              :class="[
                isNpc ? 'ra text-4xl ra-player text-cyan-400/80' :
                isExit ? 'ra text-3xl ' + (isEntityLocked ? 'ra-lock text-rose-400/80' : 'ra-double-doors text-cyan-400/80') :
                'ra text-4xl ra-vest text-amber-400/80'
              ]"
            ></i>
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(148,163,184,0.12),transparent_65%)]"></div>
          </div>

          <!-- NPC: two-column layout below image -->
          <template v-if="props.hoveredEntity.entity_type?.toUpperCase() === 'NPC'">
            <div :class="['min-h-0 overflow-y-auto', hasHeroImage ? 'tooltip-content-overlap' : '']">
              <div class="flex gap-0 min-h-0">
                <!-- Left: Name + Type + Stats -->
                <div class="flex flex-col p-3 gap-2 w-[52%] shrink-0">
                  <div class="text-xs font-black text-white uppercase tracking-wider leading-tight tooltip-readable-text">{{ props.hoveredEntity.name }}</div>
                  <div class="flex flex-col gap-1">
                    <StatBar v-if="props.hoveredEntity.hp != null" label="HP" :value="Number(props.hoveredEntity.hp)" :max="Number(props.hoveredEntity.max_hp || 100)" color="crimson" size="sm" />
                    <StatBar v-if="props.hoveredEntity.stamina != null" label="STA" :value="Number(props.hoveredEntity.stamina)" :max="Number(props.hoveredEntity.max_stamina || 100)" color="emerald" size="sm" />
                    <StatBar v-if="props.hoveredEntity.mana != null && props.ruleMode === 'rpg'" label="MP" :value="Number(props.hoveredEntity.mana)" :max="Number(props.hoveredEntity.max_mana || 100)" color="sapphire" size="sm" />
                  </div>
                  <!-- Possessions -->
                  <div v-if="Array.isArray(props.hoveredEntity.inventory) && props.hoveredEntity.inventory.length > 0" class="pt-1 border-t border-slate-800">
                    <div class="text-xxs font-black uppercase tracking-widest text-slate-500 mb-1">Items</div>
                    <div class="flex flex-wrap gap-1">
                      <div
                        v-for="(item, iidx) in props.hoveredEntity.inventory.slice(0, 4)"
                        :key="item?.id || iidx"
                        class="px-1.5 py-0.5 rounded bg-slate-950/60 border border-slate-800 text-xxs text-slate-300 flex items-center gap-1"
                      >
                        <i :class="['ra text-[10px]', getItemIcon(typeof item === 'object' ? item?.item_type || 'PICKABLE' : 'PICKABLE'), 'text-amber-500/60']"></i>
                        {{ typeof item === 'object' ? item?.name : item }}
                      </div>
                      <div v-if="props.hoveredEntity.inventory.length > 4" class="text-xxs text-slate-600 self-center">+{{ props.hoveredEntity.inventory.length - 4 }}</div>
                    </div>
                  </div>
                </div>
                <!-- Right: Description -->
                <div class="p-3 flex-1 min-w-0">
                  <p class="text-[13px] text-slate-400 leading-relaxed italic whitespace-pre-wrap break-words tooltip-readable-text" v-html="formatObjectIds(props.hoveredEntity.description)"></p>
                </div>
              </div>
            </div>
          </template>

          <!-- Non-NPC: original single-column layout -->
          <template v-else>
          <div :class="['min-h-0 overflow-y-auto', hasHeroImage ? 'tooltip-content-overlap' : '']">
            <div :class="['flex items-center justify-between mb-1', headerPaddingClass]">
              <span :class="['font-bold text-white uppercase tracking-wider', headerLabelClass]">{{ entityName }}</span>
              <span
                class="text-xxs px-1.5 py-0.5 rounded border font-mono uppercase"
                :class="badgeBorderClass"
              >
                {{ entityTypeLabel }}
              </span>
            </div>

            <div :class="bodyPaddingClass">
              <p :class="['text-slate-300 leading-relaxed italic whitespace-pre-wrap break-words tooltip-readable-text', bodyTextClass]"
                 v-html="formatObjectIds(entityDescription)"></p>

              <p v-if="isExit && isEntityLocked"
                 class="text-[11px] uppercase tracking-widest text-rose-300 font-bold border-t border-slate-800 pt-2 mt-2 flex items-center gap-1.5">
                <i class="ra ra-lock text-rose-400"></i>
                This exit is locked
              </p>
            </div>

            <div v-if="(props.hoveredEntity.entity_type === 'OBJECT' || props.hoveredEntity.entity_type === 'ITEM') && props.ruleMode !== 'chat' && hasObjectDetails" :class="detailsPaddingClass">
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
          </template>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.tooltip-enter-active,
.tooltip-leave-active {
  transition: opacity 260ms ease, transform 360ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: opacity, transform;
}

.tooltip-enter-from,
.tooltip-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.975);
}

.tooltip-enter-to,
.tooltip-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.animate-tooltip-in {
  animation: toolTipIn 360ms cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(12px) scale(0.965); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.tooltip-content-overlap {
  margin-top: -4.5rem;
  position: relative;
  z-index: 10;
  background: linear-gradient(
    to bottom,
    rgba(2, 6, 23, 0.04) 0%,
    rgba(2, 6, 23, 0.18) 18%,
    rgba(2, 6, 23, 0.5) 42%,
    rgba(15, 23, 42, 0.86) 70%,
    rgba(15, 23, 42, 0.98) 100%
  );
}

.tooltip-image-fray {
  pointer-events: none;
  background:
    radial-gradient(140% 90% at 50% 0%, rgba(15, 23, 42, 0.18) 0%, rgba(15, 23, 42, 0.65) 52%, rgba(15, 23, 42, 0.96) 100%),
    linear-gradient(to bottom, rgba(148, 163, 184, 0.2) 0%, rgba(148, 163, 184, 0) 45%);
  filter: blur(1.35px);
}
.tooltip-readable-text {
  text-shadow: 0 2px 4px rgba(2, 6, 23, 0.98), 0 0 12px rgba(15, 23, 42, 0.65);
}
</style>
