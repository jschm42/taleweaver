<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronRight, Lock, Plus, Save, Trash2 } from 'lucide-vue-next'
import type { SpecialAttack } from '@/types'
import SpecialAttackForm, { type SpecialAttackDraft } from '@/components/editor/SpecialAttackForm.vue'
import { specialAttackService, type SpecialAttackOwner } from '@/services/specialAttackService'
import {
  AMOUNT_PATTERN,
  CATEGORY_META,
  checkLabel,
  costLabel,
  describeEffects,
  normalizeSpecialAttack,
} from '@/utils/specialAttacks'

const MAX_ATTACKS = 8
const ID_PATTERN = /^[A-Z0-9_-]{1,128}$/
// Fields accepted by the backend schema (extra fields are rejected there).
const SCHEMA_KEYS: Array<keyof SpecialAttack> = [
  'id', 'name', 'description', 'action_type', 'category', 'cost_type', 'cost', 'mana_cost',
  'success_stat', 'difficulty', 'effects', 'target_scope', 'splash_radius', 'save_stat', 'spares_passive',
  'outcome_description', 'is_locked',
  'unlock_condition_type', 'unlock_condition_target', 'unlock_required_item_id',
  'unlock_required_scene_id', 'unlock_required_defeated_npc_id', 'unlock_guard_expression',
  'unlock_text', 'on_success_script', 'on_success_text', 'on_failure_script', 'on_failure_text',
]

const props = defineProps<{
  adventureId: string
  targetType: SpecialAttackOwner
  targetId: string
  ownerName: string
  attacks: SpecialAttack[]
  referenceOptions?: Array<{ id: string; name?: string; type?: string }>
}>()

const emit = defineEmits<{
  saved: [attacks: SpecialAttack[]]
}>()

let keyCounter = 0
const drafts = ref<SpecialAttackDraft[]>([])
const expanded = ref<number | null>(null)
const saving = ref(false)
const error = ref('')
const savedNote = ref('')

const PRESETS: Record<string, Omit<SpecialAttack, 'id'>> = {
  Fireball: {
    name: 'Fireball', description: 'A roaring ball of flame.', action_type: 'ATTACK', category: 'MAGIC',
    cost_type: 'mana', cost: 25, effects: [{ target: 'target', stat: 'hp', amount: '-3d6' }],
    // Area settings only apply to the protagonist; NPCs keep a single-target fireball.
    target_scope: 'ALL_ENEMIES', save_stat: 'dexterity', difficulty: 13,
  },
  'Shield Bash': {
    name: 'Shield Bash', description: 'Slams the shield into the foe, leaving it dazed.', action_type: 'ATTACK',
    category: 'MELEE', cost_type: 'stamina', cost: 20,
    effects: [{ target: 'target', stat: 'hp', amount: '-1d6' }, { target: 'target', stat: 'dexterity', amount: '-2' }],
  },
  Insult: {
    name: 'Withering Insult', description: 'Words sharper than any blade.', action_type: 'UTILITY', category: 'SOCIAL',
    cost_type: 'stamina', cost: 10, success_stat: 'charisma',
    effects: [{ target: 'target', stat: 'charisma', amount: '-3' }, { target: 'target', stat: 'hp', amount: '-2' }],
  },
  'Battle Cry': {
    name: 'Battle Cry', description: 'A roar that steels the body.', action_type: 'UTILITY', category: 'OTHER',
    cost_type: 'stamina', cost: 15,
    effects: [{ target: 'self', stat: 'strength', amount: '+2' }, { target: 'self', stat: 'armor_class', amount: '+1' }],
  },
  Heal: {
    name: 'Mend Wounds', description: 'Soothing light closes wounds.', action_type: 'HEAL', category: 'MAGIC',
    cost_type: 'mana', cost: 15, effects: [{ target: 'self', stat: 'hp', amount: '+2d8' }],
  },
}

function toDraft(attack: SpecialAttack): SpecialAttackDraft {
  const n = normalizeSpecialAttack(attack)
  return {
    ...attack,
    category: n.category,
    cost_type: n.cost_type,
    cost: n.cost,
    success_stat: n.success_stat,
    effects: n.effects.map((e) => ({ ...e })),
    // The form uses null for "single target" and "no saving throw".
    target_scope: n.target_scope === 'SINGLE' ? null : n.target_scope,
    splash_radius: n.splash_radius,
    save_stat: attack.save_stat ?? null,
    spares_passive: !!attack.spares_passive,
    on_success_script: attack.on_success_script ?? '',
    on_failure_script: attack.on_failure_script ?? '',
    _key: ++keyCounter,
  }
}

// Keyed by content so parents may pass freshly built arrays without wiping unsaved edits.
watch(() => `${props.targetId}:${JSON.stringify(props.attacks ?? [])}`, () => {
  drafts.value = (props.attacks ?? []).map(toDraft)
  expanded.value = null
}, { immediate: true })

function slugify(name: string): string {
  return name.toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 60) || 'SPECIAL'
}

function uniqueId(base: string): string {
  const taken = new Set(drafts.value.map((d) => d.id))
  let candidate = base
  for (let n = 2; taken.has(candidate); n += 1) candidate = `${base}_${n}`
  return candidate
}

function addAttack(presetName?: string): void {
  if (drafts.value.length >= MAX_ATTACKS) return
  const preset = presetName ? PRESETS[presetName] : null
  const base: SpecialAttack = preset
    ? { ...preset, effects: preset.effects?.map((e) => ({ ...e })), id: '' }
    : { id: '', name: 'New Attack', action_type: 'ATTACK', category: 'MELEE', cost_type: 'stamina', cost: 10, effects: [{ target: 'target', stat: 'hp', amount: '-1d6' }] }
  base.id = uniqueId(slugify(base.name))
  drafts.value.push(toDraft(base))
  expanded.value = drafts.value[drafts.value.length - 1]._key
}

function removeAttack(key: number): void {
  drafts.value = drafts.value.filter((d) => d._key !== key)
}

const problems = computed(() => {
  const issues: string[] = []
  const ids = new Set<string>()
  for (const d of drafts.value) {
    if (!d.name.trim()) issues.push('Every attack needs a name.')
    if (!ID_PATTERN.test(d.id)) issues.push(`"${d.name}": ID may only use A-Z, 0-9, _ and -.`)
    if (ids.has(d.id)) issues.push(`Duplicate ID ${d.id}.`)
    ids.add(d.id)
    if (d.effects.some((e) => !AMOUNT_PATTERN.test(e.amount.replace(/\s/g, '')))) {
      issues.push(`"${d.name}": amounts must look like -2d6, +5 or -3.`)
    }
  }
  return issues
})

function serialize(d: SpecialAttackDraft): SpecialAttack {
  const out: Record<string, unknown> = {}
  for (const key of SCHEMA_KEYS) {
    const value = d[key]
    if (value !== undefined && value !== null && value !== '') out[key] = value
  }
  const cost = Math.max(0, Number(d.cost) || 0)
  // Area settings only exist on protagonist area attacks; drop leftovers otherwise.
  const isArea = props.targetType === 'protagonist' && !!d.target_scope && d.target_scope !== 'SINGLE'
  if (!isArea) {
    for (const key of ['target_scope', 'splash_radius', 'save_stat', 'spares_passive'] as const) delete out[key]
  } else if (d.target_scope !== 'SPLASH') {
    delete out.splash_radius
  }
  return {
    ...(out as unknown as SpecialAttack),
    id: d.id.trim().toUpperCase(),
    name: d.name.trim(),
    description: d.description ?? '',
    cost,
    mana_cost: d.cost_type === 'mana' ? cost : 0,
    difficulty: d.difficulty ? Number(d.difficulty) : null,
    is_locked: props.targetType === 'protagonist' && !!d.is_locked,
    effects: d.effects.map((e) => ({ ...e, amount: e.amount.replace(/\s/g, '') })),
  }
}

async function save(): Promise<void> {
  if (problems.value.length) return
  saving.value = true
  error.value = ''
  savedNote.value = ''
  try {
    const saved = await specialAttackService.save(props.adventureId, props.targetType, props.targetId, drafts.value.map(serialize))
    savedNote.value = 'Saved.'
    emit('saved', saved)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save.'
  } finally {
    saving.value = false
  }
}

function summary(d: SpecialAttackDraft): string {
  const n = normalizeSpecialAttack(d)
  return `${costLabel(n)} · ${checkLabel(n)} · ${describeEffects(d.effects) || 'no effects'}`
}
</script>

<template>
  <section class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h4 class="text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Special Attacks · {{ ownerName }}</h4>
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="text-[10px] text-slate-500 uppercase tracking-widest mr-1">Add</span>
        <button
          v-for="name in Object.keys(PRESETS)"
          :key="name"
          type="button"
          class="px-2 py-1 rounded-lg border border-white/10 bg-slate-800/60 text-[11px] font-bold text-slate-300 hover:border-emerald-400/50 hover:text-white disabled:opacity-40"
          :disabled="drafts.length >= MAX_ATTACKS"
          @click="addAttack(name)"
        >{{ name }}</button>
        <button
          type="button"
          class="px-2 py-1 rounded-lg border border-emerald-500/40 bg-emerald-950/40 text-[11px] font-bold text-emerald-300 flex items-center gap-1 disabled:opacity-40"
          :disabled="drafts.length >= MAX_ATTACKS"
          @click="addAttack()"
        ><Plus class="w-3 h-3" /> Blank</button>
      </div>
    </div>

    <p v-if="!drafts.length" class="text-xs text-slate-500 italic">No special attacks yet. Add a preset or start from scratch.</p>

    <article v-for="(d, idx) in drafts" :key="d._key" class="rounded-xl border border-white/10 bg-slate-950/40">
      <header class="flex items-center gap-2 px-3 py-2 cursor-pointer" @click="expanded = expanded === d._key ? null : d._key">
        <component :is="expanded === d._key ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-500" />
        <i :class="['ra text-base text-slate-300', CATEGORY_META[normalizeSpecialAttack(d).category].icon]"></i>
        <span class="font-bold text-sm text-white truncate">{{ d.name || 'Unnamed' }}</span>
        <Lock v-if="targetType === 'protagonist' && d.is_locked" class="w-3.5 h-3.5 text-amber-400" />
        <span class="text-[10px] font-mono text-slate-400 truncate">{{ summary(d) }}</span>
        <button type="button" class="ml-auto p-1 text-slate-500 hover:text-rose-400" title="Remove attack" @click.stop="removeAttack(d._key)">
          <Trash2 class="w-4 h-4" />
        </button>
      </header>
      <SpecialAttackForm
        v-if="expanded === d._key"
        v-model="drafts[idx]"
        :is-protagonist="targetType === 'protagonist'"
        :reference-options="referenceOptions"
      />
    </article>

    <div class="flex flex-wrap items-center gap-3">
      <button
        type="button"
        class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-wider flex items-center gap-2 disabled:opacity-40"
        :disabled="saving || problems.length > 0"
        @click="save"
      >
        <Save class="w-3.5 h-3.5" /> {{ saving ? 'Saving…' : 'Save Special Attacks' }}
      </button>
      <span v-if="savedNote" class="text-xs text-emerald-400">{{ savedNote }}</span>
      <span v-if="error" class="text-xs text-rose-400">{{ error }}</span>
      <span v-for="p in problems" :key="p" class="text-xs text-amber-400">{{ p }}</span>
    </div>
  </section>
</template>
