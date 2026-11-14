<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronRight, Lock, Plus, Save, Sparkles, Trash2 } from 'lucide-vue-next'
import type { Talent } from '@/types'
import TalentForm, { type TalentDraft } from '@/components/editor/TalentForm.vue'
import { specialAttackService } from '@/services/specialAttackService'
import { MAX_TALENTS, TALENT_TARGET_LABELS, normalizeTalent, talentCostLabel } from '@/utils/talents'
import {
  EDITOR_ID_PREFIXES,
  MAX_EDITOR_ID_LENGTH,
  generateEditorId,
  isValidEditorId,
} from '@/utils/editor_utils'
// Fields accepted by the backend schema (extra fields are rejected there).
const SCHEMA_KEYS: Array<keyof Talent> = [
  'id', 'name', 'description', 'target_type', 'cost_type', 'cost', 'max_uses', 'gm_hint',
  'on_use_script', 'on_use_text', 'is_locked', 'unlock_required_item_id', 'unlock_required_scene_id',
  'unlock_required_defeated_npc_id', 'unlock_guard_expression', 'unlock_text',
]

const props = defineProps<{
  adventureId: string
  ownerName: string
  talents: Talent[]
  referenceOptions?: Array<{ id: string; name?: string; type?: string }>
}>()

const emit = defineEmits<{ saved: [talents: Talent[]] }>()

let keyCounter = 0
const drafts = ref<TalentDraft[]>([])
const expanded = ref<number | null>(null)
const saving = ref(false)
const error = ref('')
const savedNote = ref('')

const PRESETS: Record<string, Omit<Talent, 'id'>> = {
  'Mind Reading': {
    name: 'Mind Reading', description: 'Hear what a person really thinks for a moment.', target_type: 'NPC',
    cost_type: 'mana', cost: 10, gm_hint: "Reveal the target's true thoughts in one short italic sentence.",
  },
  'Gossip Attack': {
    name: 'Gossip Attack', description: 'Spread a vicious rumour about someone present.', target_type: 'NPC',
    cost_type: 'stamina', cost: 5,
    gm_hint: 'The rumour spreads instantly; bystanders whisper and the target loses face.',
  },
  'Animal Whisperer': {
    name: 'Animal Whisperer', description: 'Talk to any animal.', target_type: 'NPC', cost_type: 'mana', cost: 5,
    gm_hint: 'Animals can answer in simple words and may share what they have seen.',
  },
  'Lucky Hunch': {
    name: 'Lucky Hunch', description: 'A sudden gut feeling about what to do next.', target_type: 'NONE',
    cost_type: 'mana', cost: 0, max_uses: 3, gm_hint: 'Give the player one honest, concrete hint about the next step.',
  },
}

function toDraft(talent: Talent): TalentDraft {
  const n = normalizeTalent(talent)
  return {
    ...talent,
    target_type: n.target_type,
    cost_type: n.cost_type,
    cost: n.cost,
    max_uses: n.max_uses,
    gm_hint: talent.gm_hint ?? '',
    on_use_script: talent.on_use_script ?? '',
    on_use_text: talent.on_use_text ?? '',
    _key: ++keyCounter,
  }
}

// Keyed by content so parents may pass freshly built arrays without wiping unsaved edits.
watch(() => JSON.stringify(props.talents ?? []), () => {
  drafts.value = (props.talents ?? []).map(toDraft)
  expanded.value = null
}, { immediate: true })

function addTalent(presetName?: string): void {
  if (drafts.value.length >= MAX_TALENTS) return
  const preset = presetName ? PRESETS[presetName] : null
  const base: Talent = preset
    ? { ...preset, id: '' }
    : { id: '', name: 'New Talent', description: '', target_type: 'NONE', cost_type: 'mana', cost: 5 }
  base.id = generateEditorId({
    prefix: EDITOR_ID_PREFIXES.TALENT,
    sourceName: base.name,
    takenIds: drafts.value.map((d) => d.id),
    maxLen: MAX_EDITOR_ID_LENGTH,
  })
  drafts.value.push(toDraft(base))
  expanded.value = drafts.value[drafts.value.length - 1]._key
}

function removeTalent(key: number): void {
  drafts.value = drafts.value.filter((d) => d._key !== key)
}

const problems = computed(() => {
  const issues: string[] = []
  const ids = new Set<string>()
  const names = new Set<string>()
  for (const d of drafts.value) {
    const name = d.name.trim().toLowerCase()
    if (!name) issues.push('Every talent needs a name.')
    if (!d.description?.trim()) issues.push(`"${d.name}": add a description.`)
    if (!isValidEditorId(d.id.toUpperCase(), MAX_EDITOR_ID_LENGTH)) {
      issues.push(`"${d.name}": ID must use A-Z, 0-9, and _ only (max ${MAX_EDITOR_ID_LENGTH} chars).`)
    }
    if (ids.has(d.id.toUpperCase())) issues.push(`Duplicate ID ${d.id}.`)
    if (name && names.has(name)) issues.push(`Two talents are called "${d.name}".`)
    ids.add(d.id.toUpperCase())
    names.add(name)
  }
  return issues
})

function serialize(d: TalentDraft): Talent {
  const out: Record<string, unknown> = {}
  for (const key of SCHEMA_KEYS) {
    const value = d[key]
    if (value !== undefined && value !== null && value !== '') out[key] = value
  }
  const maxUses = Number(d.max_uses)
  return {
    ...(out as unknown as Talent),
    id: d.id.trim().toUpperCase(),
    name: d.name.trim(),
    description: (d.description ?? '').trim(),
    cost: Math.max(0, Number(d.cost) || 0),
    max_uses: Number.isInteger(maxUses) && maxUses > 0 ? maxUses : null,
    is_locked: !!d.is_locked,
  }
}

async function save(): Promise<void> {
  if (problems.value.length) return
  saving.value = true
  error.value = ''
  savedNote.value = ''
  try {
    const saved = await specialAttackService.saveTalents(props.adventureId, drafts.value.map(serialize))
    savedNote.value = 'Saved.'
    emit('saved', saved)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save.'
  } finally {
    saving.value = false
  }
}

function summary(d: TalentDraft): string {
  const n = normalizeTalent(d)
  const uses = n.max_uses ? `${n.max_uses}× per adventure` : 'unlimited'
  return `${talentCostLabel(n)} · ${TALENT_TARGET_LABELS[n.target_type]} · ${uses}`
}
</script>

<template>
  <section class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h4 class="text-xs font-black text-violet-400 uppercase tracking-[0.2em] flex items-center gap-2">
        <Sparkles class="w-4 h-4" /> Talents · {{ ownerName }}
      </h4>
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="text-[10px] text-slate-500 uppercase tracking-widest mr-1">Add</span>
        <button
          v-for="name in Object.keys(PRESETS)"
          :key="name"
          type="button"
          class="px-2 py-1 rounded-lg border border-white/10 bg-slate-800/60 text-[11px] font-bold text-slate-300 hover:border-violet-400/50 hover:text-white disabled:opacity-40"
          :disabled="drafts.length >= MAX_TALENTS"
          @click="addTalent(name)"
        >{{ name }}</button>
        <button
          type="button"
          class="px-2 py-1 rounded-lg border border-violet-500/40 bg-violet-950/40 text-[11px] font-bold text-violet-300 flex items-center gap-1 disabled:opacity-40"
          :disabled="drafts.length >= MAX_TALENTS"
          @click="addTalent()"
        ><Plus class="w-3 h-3" /> Blank</button>
      </div>
    </div>
    <p class="text-[11px] text-slate-500">
      Non-combat abilities the player triggers from the Talents menu, the right-click menu of an NPC or item,
      or by typing "use &lt;talent&gt;" / "cast &lt;talent&gt; on &lt;target&gt;". The engine pays the cost and runs
      the script; the Game Master then narrates the effect.
    </p>

    <p v-if="!drafts.length" class="text-xs text-slate-500 italic">No talents yet. Add a preset or start from scratch.</p>

    <article v-for="(d, idx) in drafts" :key="d._key" class="rounded-xl border border-white/10 bg-slate-950/40">
      <header class="flex items-center gap-2 px-3 py-2 cursor-pointer" @click="expanded = expanded === d._key ? null : d._key">
        <component :is="expanded === d._key ? ChevronDown : ChevronRight" class="w-4 h-4 text-slate-500" />
        <span class="font-bold text-sm text-white truncate">{{ d.name || 'Unnamed' }}</span>
        <Lock v-if="d.is_locked" class="w-3.5 h-3.5 text-amber-400" />
        <span class="text-[10px] font-mono text-slate-400 truncate">{{ summary(d) }}</span>
        <button type="button" class="ml-auto p-1 text-slate-500 hover:text-rose-400" title="Remove talent" @click.stop="removeTalent(d._key)">
          <Trash2 class="w-4 h-4" />
        </button>
      </header>
      <TalentForm
        v-if="expanded === d._key"
        v-model="drafts[idx]"
        :reference-options="referenceOptions"
        :taken-ids="drafts.filter((o) => o._key !== d._key).map((o) => o.id)"
      />
    </article>

    <div class="flex flex-wrap items-center gap-3">
      <button
        type="button"
        class="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-black uppercase tracking-wider flex items-center gap-2 disabled:opacity-40"
        :disabled="saving || problems.length > 0"
        @click="save"
      >
        <Save class="w-3.5 h-3.5" /> {{ saving ? 'Saving…' : 'Save Talents' }}
      </button>
      <span v-if="savedNote" class="text-xs text-emerald-400">{{ savedNote }}</span>
      <span v-if="error" class="text-xs text-rose-400">{{ error }}</span>
      <span v-for="p in problems" :key="p" class="text-xs text-amber-400">{{ p }}</span>
    </div>
  </section>
</template>
