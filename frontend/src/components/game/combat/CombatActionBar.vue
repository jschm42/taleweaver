<script setup lang="ts">
import { computed } from 'vue'
import { Footprints, Lock } from 'lucide-vue-next'
import type { CharacterSheet, CombatState, InventoryItem, NormalizedSpecialAttack } from '@/types'
import { getImageUrl, getItemIcon, getTypeColor, hasRenderableImagePath } from '@/utils/game_icons'
import {
  CATEGORY_META,
  checkLabel,
  costLabel,
  describeEffects,
  normalizeSpecialAttack,
} from '@/utils/specialAttacks'

const props = defineProps<{
  combat: CombatState
  playerSheet: CharacterSheet | null
  consumables: InventoryItem[]
  locked: boolean
  targetName: string | null
}>()

const emit = defineEmits<{
  attack: []
  special: [id: string]
  consume: [name: string]
  rest: []
  run: []
  hover: [entity: Record<string, unknown>, event: MouseEvent]
  leave: []
}>()

const TONE_CLASSES: Record<string, string> = {
  violet: 'border-violet-500/40 from-violet-950/50 hover:border-violet-300/70 text-violet-100 hover:shadow-[0_0_16px_rgba(167,139,250,0.35)]',
  orange: 'border-orange-500/40 from-orange-950/50 hover:border-orange-300/70 text-orange-100 hover:shadow-[0_0_16px_rgba(251,146,60,0.35)]',
  green: 'border-green-500/40 from-green-950/50 hover:border-green-300/70 text-green-100 hover:shadow-[0_0_16px_rgba(74,222,128,0.35)]',
  pink: 'border-pink-500/40 from-pink-950/50 hover:border-pink-300/70 text-pink-100 hover:shadow-[0_0_16px_rgba(244,114,182,0.35)]',
  cyan: 'border-cyan-500/40 from-cyan-950/50 hover:border-cyan-300/70 text-cyan-100 hover:shadow-[0_0_16px_rgba(34,211,238,0.35)]',
}

function num(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

const resources = computed(() => ({
  mana: num(props.combat.player?.mana, num(props.playerSheet?.mana)),
  stamina: num(props.combat.player?.stamina, num(props.playerSheet?.stamina)),
}))

const weapon = computed(() => {
  const eq = props.playerSheet?.equipment || {}
  const item = (eq.MainHand || eq.main_hand || null) as InventoryItem | null
  const meta = ((item?.metadata_json as Record<string, unknown>) || {}) as Record<string, unknown>
  const costType = meta.weapon_cost_type === 'mana' ? 'mana' : 'stamina'
  return {
    name: item?.name || 'Bare Fists',
    dice: String(meta.damage_dice || item?.damage_dice || '1d8'),
    costType,
    cost: num(meta.weapon_cost_value, 20),
  } as const
})

const canAffordWeapon = computed(() => resources.value[weapon.value.costType] >= weapon.value.cost)

const specials = computed<NormalizedSpecialAttack[]>(() => {
  const fromCombat = props.combat.player?.special_actions
  if (fromCombat?.length) return fromCombat
  const unlocked = new Set(props.playerSheet?.unlocked_actions ?? [])
  return (props.playerSheet?.special_actions ?? []).map((a) => ({
    ...normalizeSpecialAttack(a),
    locked: !unlocked.has(a.id),
  }))
})

function canUse(action: NormalizedSpecialAttack): boolean {
  if (action.locked) return false
  if (action.targets_enemy && !props.targetName) return false
  return resources.value[action.cost_type] >= action.cost
}

function specialClass(action: NormalizedSpecialAttack): string {
  if (!canUse(action) || props.locked) return 'border-slate-800 from-slate-950/40 text-slate-500 cursor-not-allowed'
  return `${TONE_CLASSES[CATEGORY_META[action.category].tone]} hover:-translate-y-0.5`
}

function specialTooltip(action: NormalizedSpecialAttack): Record<string, unknown> {
  const lockNote = action.locked ? ` (Locked${action.unlock_condition_target ? `: requires ${action.unlock_condition_target}` : ''})` : ''
  return {
    id: action.id,
    entity_type: 'ITEM',
    item_type: 'SPECIAL',
    name: `${action.name}${lockNote}`,
    description: [
      action.description,
      `Cost: ${costLabel(action)} · Check: ${checkLabel(action)}`,
      `Effects: ${describeEffects(action.effects) || 'narrative only'}`,
    ].filter(Boolean).join('\n'),
  }
}

function consumableTooltip(item: InventoryItem): Record<string, unknown> {
  return { ...item, entity_type: 'ITEM', description: (item.description as string) || 'A consumable that can be used during combat.' }
}

const restHighlighted = computed(() => resources.value.stamina < weapon.value.cost)
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-[200px_1fr_180px] gap-3 items-stretch">
    <!-- Weapon attack -->
    <button
      type="button"
      class="group flex flex-col justify-between p-3 rounded-xl border bg-gradient-to-br to-slate-950/40 text-left transition-all"
      :class="locked || !canAffordWeapon || !targetName
        ? 'border-slate-800 from-slate-950/30 text-slate-500 cursor-not-allowed'
        : 'border-emerald-500/40 from-emerald-950/40 text-emerald-100 hover:border-emerald-300/70 hover:shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:-translate-y-0.5'"
      :disabled="locked || !canAffordWeapon || !targetName"
      @click="emit('attack')"
    >
      <span class="flex items-center justify-between text-[10px] uppercase tracking-[0.2em] font-black opacity-80">
        Attack
        <span class="px-1.5 py-0.5 rounded border border-current/30 font-mono">{{ weapon.cost }} {{ weapon.costType === 'mana' ? 'MP' : 'STA' }}</span>
      </span>
      <span class="flex items-center gap-2 my-1.5">
        <i class="ra ra-sword text-xl"></i>
        <span class="font-bold truncate">{{ weapon.name }}</span>
      </span>
      <span class="text-[11px] opacity-80 truncate">
        {{ weapon.dice }} dmg → {{ targetName || 'no target' }}
      </span>
    </button>

    <!-- Specials + consumables -->
    <div class="flex flex-col gap-2 min-w-0">
      <div class="flex flex-wrap gap-2">
        <button
          v-for="action in specials"
          :key="action.id"
          type="button"
          class="relative flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg border bg-gradient-to-br to-slate-950/40 text-left transition-all min-w-[150px] max-w-[230px]"
          :class="specialClass(action)"
          :disabled="locked || !canUse(action)"
          @click="emit('special', action.id)"
          @mouseenter="emit('hover', specialTooltip(action), $event)"
          @mousemove="emit('hover', specialTooltip(action), $event)"
          @mouseleave="emit('leave')"
        >
          <Lock v-if="action.locked" class="absolute top-1 right-1 w-3 h-3 text-slate-500" />
          <i :class="['ra text-lg shrink-0', CATEGORY_META[action.category].icon]"></i>
          <span class="min-w-0">
            <span class="block text-xs font-bold truncate">{{ action.name }}</span>
            <span class="block text-[10px] opacity-80 font-mono truncate">{{ costLabel(action) }} · {{ checkLabel(action) }}</span>
          </span>
        </button>
        <span v-if="specials.length === 0" class="text-xs text-slate-500 italic self-center">No special attacks configured.</span>
      </div>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="item in consumables"
          :key="item.id || item.name"
          type="button"
          class="flex items-center gap-2 px-2 py-1 rounded-lg border border-cyan-500/30 bg-cyan-950/30 hover:border-cyan-300/60 disabled:opacity-40 transition-all"
          :disabled="locked"
          @click="emit('consume', item.name)"
          @mouseenter="emit('hover', consumableTooltip(item), $event)"
          @mousemove="emit('hover', consumableTooltip(item), $event)"
          @mouseleave="emit('leave')"
        >
          <span class="w-6 h-6 rounded overflow-hidden border border-cyan-500/30 bg-slate-950 flex items-center justify-center shrink-0">
            <img v-if="hasRenderableImagePath(item.image_url as string)" :src="getImageUrl(item.image_url as string)" class="w-full h-full object-cover" :alt="item.name">
            <i v-else :class="['ra text-xs', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
          </span>
          <span class="text-xs font-bold text-cyan-100 truncate max-w-24">{{ item.name }}</span>
        </button>
      </div>
    </div>

    <!-- Rest & run -->
    <div class="grid grid-cols-2 lg:grid-cols-1 gap-2">
      <button
        type="button"
        class="flex items-center justify-center gap-2 px-3 py-2 rounded-xl border text-sm font-bold transition-all disabled:opacity-40"
        :class="restHighlighted ? 'border-emerald-400/70 bg-emerald-950/40 text-emerald-100 animate-pulse' : 'border-slate-700 bg-slate-900/60 text-slate-200 hover:border-slate-400/60'"
        :disabled="locked"
        @click="emit('rest')"
      >
        <i class="ra ra-hourglass"></i> Rest <span class="text-[10px] font-mono opacity-70">+40 STA</span>
      </button>
      <button
        type="button"
        class="flex items-center justify-center gap-2 px-3 py-2 rounded-xl border border-slate-700 bg-slate-900/60 text-slate-200 hover:border-rose-600/60 hover:bg-rose-950/30 text-sm font-bold transition-all disabled:opacity-40"
        :disabled="locked"
        @click="emit('run')"
      >
        <Footprints class="w-4 h-4 text-rose-300" /> Flee
      </button>
    </div>
  </div>
</template>
