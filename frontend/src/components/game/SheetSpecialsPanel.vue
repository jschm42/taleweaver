<script setup lang="ts">
import { computed } from 'vue'
import { Lock } from 'lucide-vue-next'
import type { CharacterSheet, NormalizedSpecialAttack, SpecialAttack } from '@/types'
import { CATEGORY_META, STAT_SHORT, checkLabel, costLabel, normalizeSpecialAttack } from '@/utils/specialAttacks'

const props = defineProps<{
  sheet: CharacterSheet | null
  isDebug?: boolean
}>()

type SpecialView = NormalizedSpecialAttack & { raw: SpecialAttack }

const specials = computed<SpecialView[]>(() => {
  const unlocked = new Set(props.sheet?.unlocked_actions ?? [])
  return (props.sheet?.special_actions ?? []).map((raw) => ({
    ...normalizeSpecialAttack(raw),
    locked: !unlocked.has(raw.id),
    raw,
  }))
})

const available = computed(() => specials.value.filter((s) => !s.locked))
const locked = computed(() => specials.value.filter((s) => s.locked))

function effectLines(special: SpecialView): string[] {
  return special.effects.map((e) => `${e.amount} ${STAT_SHORT[e.stat]} ${e.target === 'self' ? '(you)' : '(target)'}`)
}

function unlockConditions(raw: SpecialAttack): string[] {
  const parts: string[] = []
  if (raw.unlock_required_item_id) parts.push(`obtain ${raw.unlock_required_item_id}`)
  if (raw.unlock_required_scene_id) parts.push(`reach ${raw.unlock_required_scene_id}`)
  if (raw.unlock_required_defeated_npc_id) parts.push(`defeat ${raw.unlock_required_defeated_npc_id}`)
  if (raw.unlock_guard_expression) parts.push(`guard: ${raw.unlock_guard_expression}`)
  if (raw.unlock_condition_type && raw.unlock_condition_target) {
    parts.push(`${raw.unlock_condition_type === 'READ_ITEM' ? 'read' : 'find'} ${raw.unlock_condition_target}`)
  }
  return parts
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <div v-if="!specials.length" class="tw-dialog-slot !border-solid flex-grow flex flex-col items-center justify-center p-8 text-center">
      <i class="ra ra-crystal-wand text-4xl tw-muted mb-3"></i>
      <h4 class="tw-dialog-title text-lg">No Special Attacks</h4>
      <p class="tw-muted text-xs sm:text-sm max-w-md">Your character relies on plain weapon attacks for now.</p>
    </div>

    <section v-if="available.length" class="space-y-3">
      <h4 class="tw-panel-title tw-muted">Ready to use</h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <article v-for="s in available" :key="s.id" class="tw-card p-4 border-l-4 !border-l-violet-500 flex gap-3">
          <div class="w-10 h-10 rounded-xl border border-violet-500/40 bg-violet-500/15 flex items-center justify-center shrink-0">
            <i :class="['ra text-lg text-violet-500', CATEGORY_META[s.category].icon]"></i>
          </div>
          <div class="min-w-0 space-y-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-bold">{{ s.name }}</span>
              <span class="text-[10px] font-mono px-1.5 py-0.5 rounded border border-violet-500/40 text-violet-500">{{ costLabel(s) }}</span>
              <span class="tw-muted text-[10px] font-mono">{{ checkLabel(s) }}</span>
            </div>
            <p v-if="s.description" class="text-xs">{{ s.description }}</p>
            <ul class="flex flex-wrap gap-1.5">
              <li v-for="line in effectLines(s)" :key="line" class="tw-dialog-chip">{{ line }}</li>
            </ul>
          </div>
        </article>
      </div>
    </section>

    <section v-if="locked.length" class="space-y-3">
      <h4 class="tw-panel-title tw-muted">Locked</h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <article v-for="s in locked" :key="s.id" class="tw-card p-4 flex gap-3 opacity-70">
          <div class="tw-dialog-slot w-10 h-10 flex items-center justify-center shrink-0">
            <Lock class="w-4 h-4 tw-muted" />
          </div>
          <div class="min-w-0 space-y-1">
            <span class="font-bold">{{ s.name }}</span>
            <p class="tw-muted text-xs">Unlocks through your progress in the story.</p>
            <p v-if="isDebug && unlockConditions(s.raw).length" class="text-[10px] font-mono text-amber-400/80 break-words">
              DEBUG: {{ unlockConditions(s.raw).join(' · ') }}
            </p>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
