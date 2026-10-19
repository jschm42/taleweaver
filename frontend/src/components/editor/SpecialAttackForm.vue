<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, ChevronRight, Plus, Trash2 } from 'lucide-vue-next'
import type { SpecialAttack, SpecialEffect } from '@/types'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import { AMOUNT_PATTERN, CATEGORY_META, EFFECT_STATS, SPECIAL_CATEGORIES, STAT_SHORT, SUCCESS_STATS } from '@/utils/specialAttacks'

export type SpecialAttackDraft = SpecialAttack & { effects: SpecialEffect[]; _key: number }

const props = defineProps<{
  isProtagonist: boolean
  referenceOptions?: Array<{ id: string; name?: string; type?: string }>
}>()

const draft = defineModel<SpecialAttackDraft>({ required: true })
const showScripts = ref(!!(draft.value.on_success_script || draft.value.on_failure_script || draft.value.on_success_text || draft.value.on_failure_text))

const inputClass = 'w-full bg-slate-900 border border-white/10 rounded-lg px-2 py-1.5 text-white'

const unlockRule = computed<HardRule>({
  get: () => ({
    required_item_id: draft.value.unlock_required_item_id,
    required_scene_id: draft.value.unlock_required_scene_id,
    required_defeated_npc_id: draft.value.unlock_required_defeated_npc_id,
    guard_expression: draft.value.unlock_guard_expression,
  }),
  set: (rule) => {
    draft.value.unlock_required_item_id = rule.required_item_id || null
    draft.value.unlock_required_scene_id = rule.required_scene_id || null
    draft.value.unlock_required_defeated_npc_id = rule.required_defeated_npc_id || null
    draft.value.unlock_guard_expression = rule.guard_expression || null
  },
})

function addEffect(): void {
  draft.value.effects.push({ target: 'target', stat: 'hp', amount: '-1d4' })
}

function validAmount(amount: string): boolean {
  return AMOUNT_PATTERN.test(amount.replace(/\s/g, ''))
}
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-3 px-3 pb-3 text-xs">
    <label class="space-y-1">
      <span class="text-slate-400 font-bold">Name</span>
      <input v-model="draft.name" :class="inputClass" />
    </label>
    <label class="space-y-1">
      <span class="text-slate-400 font-bold">ID</span>
      <input v-model="draft.id" :class="[inputClass, 'font-mono uppercase']" />
    </label>
    <label class="space-y-1 md:col-span-2">
      <span class="text-slate-400 font-bold">Description</span>
      <input v-model="draft.description" :class="inputClass" />
    </label>
    <label class="space-y-1">
      <span class="text-slate-400 font-bold">Category</span>
      <select v-model="draft.category" :class="inputClass">
        <option v-for="c in SPECIAL_CATEGORIES" :key="c" :value="c">{{ CATEGORY_META[c].label }}</option>
      </select>
    </label>
    <label class="space-y-1">
      <span class="text-slate-400 font-bold">Behaviour (NPC AI)</span>
      <select v-model="draft.action_type" :class="inputClass">
        <option value="ATTACK">Attack</option>
        <option value="HEAL">Heal</option>
        <option value="UTILITY">Utility</option>
      </select>
    </label>
    <div class="flex gap-2">
      <label class="space-y-1 flex-1">
        <span class="text-slate-400 font-bold">Cost</span>
        <input v-model.number="draft.cost" type="number" min="0" :class="inputClass" />
      </label>
      <label class="space-y-1 flex-1">
        <span class="text-slate-400 font-bold">Paid with</span>
        <select v-model="draft.cost_type" :class="inputClass">
          <option value="mana">Mana</option>
          <option value="stamina">Stamina</option>
        </select>
      </label>
    </div>
    <div class="flex gap-2">
      <label class="space-y-1 flex-1">
        <span class="text-slate-400 font-bold">Success roll stat</span>
        <select v-model="draft.success_stat" :class="inputClass">
          <option v-for="s in SUCCESS_STATS" :key="s" :value="s">{{ STAT_SHORT[s] }}</option>
        </select>
      </label>
      <label class="space-y-1 flex-1">
        <span class="text-slate-400 font-bold">Difficulty (DC)</span>
        <input v-model.number="draft.difficulty" type="number" min="0" placeholder="Target AC" :class="inputClass" />
      </label>
    </div>

    <div class="md:col-span-2 space-y-1.5">
      <div class="flex items-center justify-between">
        <span class="text-slate-400 font-bold">Effects on success</span>
        <button type="button" class="text-emerald-400 font-bold flex items-center gap-1" @click="addEffect"><Plus class="w-3 h-3" /> Effect</button>
      </div>
      <div v-for="(eff, idx) in draft.effects" :key="idx" class="flex items-center gap-2">
        <select v-model="eff.target" class="bg-slate-900 border border-white/10 rounded-lg px-2 py-1 text-white">
          <option value="target">Target</option>
          <option value="self">Self</option>
        </select>
        <select v-model="eff.stat" class="bg-slate-900 border border-white/10 rounded-lg px-2 py-1 text-white">
          <option v-for="s in EFFECT_STATS" :key="s" :value="s">{{ STAT_SHORT[s] }}</option>
        </select>
        <input
          v-model="eff.amount"
          placeholder="-2d6"
          class="w-28 bg-slate-900 border rounded-lg px-2 py-1 text-white font-mono"
          :class="validAmount(eff.amount) ? 'border-white/10' : 'border-rose-500/70'"
        />
        <button type="button" class="p-1 text-slate-500 hover:text-rose-400" @click="draft.effects.splice(idx, 1)"><Trash2 class="w-3.5 h-3.5" /></button>
      </div>
      <p class="text-[10px] text-slate-500">Negative amounts drain, positive amounts boost. HP/MP/STA change directly; attribute changes last until the fight ends.</p>
    </div>

    <label class="space-y-1 md:col-span-2">
      <span class="text-slate-400 font-bold">Outcome narration (optional)</span>
      <textarea v-model="draft.outcome_description" rows="2" :class="inputClass"></textarea>
    </label>

    <!-- Unlocking (protagonist only) -->
    <div v-if="props.isProtagonist" class="md:col-span-2 space-y-2">
      <label class="flex items-center gap-2 text-slate-300 font-bold">
        <input v-model="draft.is_locked" type="checkbox" class="accent-emerald-500" /> Starts locked
      </label>
      <template v-if="draft.is_locked">
        <HardRuleTriggersEditor
          v-model="unlockRule"
          :reference-options="referenceOptions"
          title="Unlock Conditions (Hard Rules)"
          description="The special attack unlocks automatically once every configured condition is met. A system message announces it."
          guard-label="Unlock Guard (Python Expression)"
          guard-help="Optional sandboxed Python condition that must also be True to unlock this special."
        />
        <label class="block space-y-1">
          <span class="text-slate-400 font-bold">Unlock message (optional)</span>
          <input v-model="draft.unlock_text" placeholder="e.g. The relic hums as ancient knowledge floods your mind." :class="inputClass" />
        </label>
        <div class="flex flex-wrap items-center gap-2 text-slate-400">
          <span class="font-bold">Legacy trigger:</span>
          <select v-model="draft.unlock_condition_type" class="bg-slate-900 border border-white/10 rounded-lg px-2 py-1 text-white">
            <option :value="null">None</option>
            <option value="READ_ITEM">Reading item</option>
            <option value="FIND_ITEM">Finding item</option>
          </select>
          <input v-if="draft.unlock_condition_type" v-model="draft.unlock_condition_target" placeholder="ITEM_ID" class="w-40 bg-slate-900 border border-white/10 rounded-lg px-2 py-1 text-white font-mono" />
        </div>
      </template>
    </div>

    <!-- Success / failure scripting -->
    <div class="md:col-span-2 space-y-2">
      <button type="button" class="flex items-center gap-1.5 text-violet-300 font-bold" @click="showScripts = !showScripts">
        <component :is="showScripts ? ChevronDown : ChevronRight" class="w-3.5 h-3.5" /> Success / failure scripting (optional)
      </button>
      <div v-if="showScripts" class="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div class="space-y-2 p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/20">
          <ScriptEditor
            :model-value="draft.on_success_script ?? ''"
            @update:model-value="(v: string) => (draft.on_success_script = v)"
            label="On Success Script"
            help-text="Runs when the success roll succeeds. `special` holds id, name, caster, target, success, crit, fumble, roll and dc."
            context="special_action"
            min-height="90px"
          />
          <input v-model="draft.on_success_text" placeholder="On success text (optional)" :class="inputClass" />
        </div>
        <div class="space-y-2 p-3 rounded-xl bg-rose-950/20 border border-rose-500/20">
          <ScriptEditor
            :model-value="draft.on_failure_script ?? ''"
            @update:model-value="(v: string) => (draft.on_failure_script = v)"
            label="On Failure Script"
            help-text="Runs when the success roll fails. The same `special` dict is available."
            context="special_action"
            min-height="90px"
          />
          <input v-model="draft.on_failure_text" placeholder="On failure text (optional)" :class="inputClass" />
        </div>
      </div>
    </div>
  </div>
</template>
