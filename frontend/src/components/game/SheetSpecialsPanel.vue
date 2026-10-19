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
    <div v-if="!specials.length" class="flex-grow flex flex-col items-center justify-center p-8 text-center bg-slate-950/40 rounded-3xl border border-slate-800/60">
      <i class="ra ra-crystal-wand text-4xl text-slate-500 mb-3"></i>
      <h4 class="text-lg font-black text-white uppercase tracking-tight font-display">No Special Attacks</h4>
      <p class="text-xs sm:text-sm text-slate-400 max-w-md">Your character relies on plain weapon attacks for now.</p>
    </div>

    <section v-if="available.length" class="space-y-3">
      <h4 class="text-xs sm:text-sm font-black text-slate-400 uppercase tracking-widest">Ready to use</h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <article v-for="s in available" :key="s.id" class="p-4 rounded-2xl border border-violet-500/30 bg-violet-950/20 flex gap-3">
          <div class="w-10 h-10 rounded-xl border border-violet-500/40 bg-slate-950 flex items-center justify-center shrink-0">
            <i :class="['ra text-lg text-violet-300', CATEGORY_META[s.category].icon]"></i>
          </div>
          <div class="min-w-0 space-y-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-bold text-white">{{ s.name }}</span>
              <span class="text-[10px] font-mono px-1.5 py-0.5 rounded border border-violet-400/30 text-violet-200">{{ costLabel(s) }}</span>
              <span class="text-[10px] font-mono text-slate-400">{{ checkLabel(s) }}</span>
            </div>
            <p v-if="s.description" class="text-xs text-slate-300">{{ s.description }}</p>
            <ul class="flex flex-wrap gap-1.5">
              <li v-for="line in effectLines(s)" :key="line" class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900/80 border border-white/5 text-slate-300">{{ line }}</li>
            </ul>
          </div>
        </article>
      </div>
    </section>

    <section v-if="locked.length" class="space-y-3">
      <h4 class="text-xs sm:text-sm font-black text-slate-500 uppercase tracking-widest">Locked</h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <article v-for="s in locked" :key="s.id" class="p-4 rounded-2xl border border-slate-800 bg-slate-950/50 flex gap-3 opacity-80">
          <div class="w-10 h-10 rounded-xl border border-slate-700 bg-slate-950 flex items-center justify-center shrink-0">
            <Lock class="w-4 h-4 text-slate-500" />
          </div>
          <div class="min-w-0 space-y-1">
            <span class="font-bold text-slate-300">{{ s.name }}</span>
            <p class="text-xs text-slate-500">Unlocks through your progress in the story.</p>
            <p v-if="isDebug && unlockConditions(s.raw).length" class="text-[10px] font-mono text-amber-400/80 break-words">
              DEBUG: {{ unlockConditions(s.raw).join(' · ') }}
            </p>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
