<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import type { SpecialAttack, SpecialEffect, SuccessStat } from '@/types'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import EditorIdInput from '@/components/editor/EditorIdInput.vue'
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import { EDITOR_ID_PREFIXES, MAX_EDITOR_ID_LENGTH } from '@/utils/editor_utils'
import {
  AMOUNT_PATTERN,
  CATEGORY_META,
  DEFAULT_SAVE_DC,
  EFFECT_STATS,
  SPECIAL_CATEGORIES,
  STAT_SHORT,
  SUCCESS_STATS,
} from '@/utils/specialAttacks'

export type SpecialAttackDraft = SpecialAttack & { effects: SpecialEffect[]; _key: number }

const props = defineProps<{
  isProtagonist: boolean
  referenceOptions?: Array<{ id: string; name?: string; type?: string }>
  takenIds?: Iterable<string>
}>()

const draft = defineModel<SpecialAttackDraft>({ required: true })
const showScripts = ref(!!(draft.value.on_success_script || draft.value.on_failure_script || draft.value.on_success_text || draft.value.on_failure_text))

const CATEGORY_OPTIONS = SPECIAL_CATEGORIES.map((c) => ({ value: c, label: CATEGORY_META[c].label }))
const ACTION_OPTIONS = [
  { value: 'ATTACK', label: 'Attack' },
  { value: 'HEAL', label: 'Heal' },
  { value: 'UTILITY', label: 'Utility' },
]
const COST_OPTIONS = [
  { value: 'mana', label: 'Mana' },
  { value: 'stamina', label: 'Stamina' },
]
const STAT_OPTIONS = SUCCESS_STATS.map((s) => ({ value: s, label: STAT_SHORT[s] }))
const SCOPE_OPTIONS = [
  { value: '', label: 'Single target' },
  { value: 'SPLASH', label: 'Splash (target + neighbours)' },
  { value: 'ALL_ENEMIES', label: 'All enemies' },
]
const RADIUS_OPTIONS = [
  { value: 1, label: '1 each side' },
  { value: 2, label: '2 each side' },
]
const SAVE_OPTIONS = [
  { value: '', label: 'None (one attack roll)' },
  ...SUCCESS_STATS.map((s) => ({ value: s, label: `${STAT_SHORT[s]} save` })),
]
const LEGACY_UNLOCK_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'READ_ITEM', label: 'Reading item' },
  { value: 'FIND_ITEM', label: 'Finding item' },
]
const EFFECT_TARGET_OPTIONS = [
  { value: 'target', label: 'Target' },
  { value: 'self', label: 'Self' },
  { value: 'ally', label: 'Ally (companion)' },
]
const EFFECT_STAT_OPTIONS = EFFECT_STATS.map((s) => ({ value: s, label: STAT_SHORT[s] }))

type ControlValue = string | number | null

function toNumber(value: ControlValue): number | null {
  return value === null || value === '' ? null : Number(value)
}

function setTargetScope(value: ControlValue): void {
  draft.value.target_scope = (value || null) as SpecialAttack['target_scope']
}

function setSaveStat(value: ControlValue): void {
  draft.value.save_stat = (value || null) as SuccessStat | null
}

function setLegacyUnlock(value: ControlValue): void {
  draft.value.unlock_condition_type = (value || null) as SpecialAttack['unlock_condition_type']
}

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

const isArea = computed(() => !!draft.value.target_scope && draft.value.target_scope !== 'SINGLE')
const hasTargetEffect = computed(() => draft.value.effects.some((e) => e.target === 'target'))
const difficultyPlaceholder = computed(() => (
  isArea.value && draft.value.save_stat ? `Save DC ${DEFAULT_SAVE_DC}` : 'Target AC'
))
const areaSummary = computed(() => {
  const save = draft.value.save_stat
  const roll = save
    ? `Every target rolls a ${STAT_SHORT[save]} save against the DC (default ${DEFAULT_SAVE_DC}) and takes half on a success.`
    : "One success roll is compared against every target's AC (or the fixed DC)."
  const splash = draft.value.target_scope === 'SPLASH' ? ' Neighbours of the chosen target take half.' : ''
  const passive = draft.value.spares_passive
    ? ' Passive NPCs in the enemy stack are left out.'
    : ' Passive NPCs in the enemy stack are hit too and join the fight.'
  return `Cost is paid once and damage is rolled once. ${roll}${splash}${passive}`
})

function addEffect(): void {
  draft.value.effects.push({ target: 'target', stat: 'hp', amount: '-1d4' })
}

function validAmount(amount: string): boolean {
  return AMOUNT_PATTERN.test(amount.replace(/\s/g, ''))
}
</script>

<template>
  <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <UiField label="Name">
      <UiInput v-model="draft.name" />
    </UiField>
    <UiField label="ID" required>
      <EditorIdInput
        v-model="draft.id"
        :prefix="EDITOR_ID_PREFIXES.ATTACK"
        :source-name="draft.name"
        :taken-ids="takenIds"
        :max-length="MAX_EDITOR_ID_LENGTH"
        :compact="true"
        :required="true"
        placeholder="ATK_CLEAVE"
        aria-label="Special attack ID"
      />
    </UiField>
    <UiField label="Description" class="md:col-span-2">
      <UiInput v-model="draft.description" />
    </UiField>
    <UiField label="Category">
      <UiSelect v-model="draft.category" :options="CATEGORY_OPTIONS" />
    </UiField>
    <UiField label="Behaviour (NPC AI)">
      <UiSelect v-model="draft.action_type" :options="ACTION_OPTIONS" />
    </UiField>
    <div class="grid grid-cols-2 gap-3">
      <UiField label="Cost">
        <UiInput type="number" min="0" :model-value="draft.cost ?? null" @update:model-value="(v) => (draft.cost = toNumber(v))" />
      </UiField>
      <UiField label="Paid with">
        <UiSelect v-model="draft.cost_type" :options="COST_OPTIONS" />
      </UiField>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <UiField label="Success roll stat">
        <UiSelect v-model="draft.success_stat" :options="STAT_OPTIONS" />
      </UiField>
      <UiField label="Difficulty (DC)">
        <UiInput
          type="number"
          min="0"
          :placeholder="difficultyPlaceholder"
          :model-value="draft.difficulty ?? null"
          @update:model-value="(v) => (draft.difficulty = toNumber(v))"
        />
      </UiField>
    </div>

    <!-- Area of effect (protagonist only; NPC specials always hit one target) -->
    <div v-if="props.isProtagonist" class="grid grid-cols-1 items-end gap-3 md:col-span-2 md:grid-cols-4">
      <UiField label="Area">
        <UiSelect :model-value="draft.target_scope ?? ''" :options="SCOPE_OPTIONS" @update:model-value="setTargetScope" />
      </UiField>
      <template v-if="isArea">
        <UiField v-if="draft.target_scope === 'SPLASH'" label="Radius">
          <UiSelect
            :model-value="draft.splash_radius ?? 1"
            :options="RADIUS_OPTIONS"
            @update:model-value="(v) => (draft.splash_radius = toNumber(v))"
          />
        </UiField>
        <UiField label="Saving throw">
          <UiSelect :model-value="draft.save_stat ?? ''" :options="SAVE_OPTIONS" @update:model-value="setSaveStat" />
        </UiField>
        <UiCheckbox
          :model-value="!!draft.spares_passive"
          label="Spare passive NPCs"
          class="pb-2"
          @update:model-value="(v) => (draft.spares_passive = v)"
        />
      </template>
      <p v-if="isArea" class="wb-hint md:col-span-4">{{ areaSummary }}</p>
      <UiNotice v-if="isArea && !hasTargetEffect" tone="warn" class="md:col-span-4">
        Area only applies to effects on "Target". Add at least one Target effect.
      </UiNotice>
    </div>

    <div class="space-y-2 md:col-span-2">
      <div class="flex items-center justify-between gap-3">
        <p class="wb-label">Effects on success</p>
        <UiButton size="sm" variant="ghost" :icon="Plus" @click="addEffect">Add effect</UiButton>
      </div>
      <div v-for="(eff, idx) in draft.effects" :key="idx" class="flex items-center gap-2">
        <UiSelect v-model="eff.target" size="sm" :options="EFFECT_TARGET_OPTIONS" class="w-40" aria-label="Effect target" />
        <UiSelect v-model="eff.stat" size="sm" :options="EFFECT_STAT_OPTIONS" class="w-28" aria-label="Effect stat" />
        <UiInput v-model="eff.amount" size="sm" class="w-28" mono placeholder="-2d6" :invalid="!validAmount(eff.amount)" aria-label="Effect amount" />
        <UiIconButton :icon="Trash2" label="Remove effect" size="sm" variant="danger" @click="draft.effects.splice(idx, 1)" />
      </div>
      <p class="wb-hint">
        Negative amounts drain, positive ones boost. HP/MP/STA change directly; attribute changes last until the fight
        ends. "Ally" is the caster's party partner.
      </p>
    </div>

    <UiField label="Outcome narration" hint="Optional." class="md:col-span-2">
      <UiTextarea :model-value="draft.outcome_description ?? ''" :rows="2" @update:model-value="(v) => (draft.outcome_description = v)" />
    </UiField>

    <!-- Unlocking (protagonist only) -->
    <div v-if="props.isProtagonist" class="space-y-4 md:col-span-2">
      <UiCheckbox :model-value="!!draft.is_locked" label="Starts locked" @update:model-value="(v) => (draft.is_locked = v)" />
      <template v-if="draft.is_locked">
        <HardRuleTriggersEditor
          v-model="unlockRule"
          :reference-options="referenceOptions"
          title="Unlock conditions"
          description="Unlocks automatically once every configured condition is met. A system message announces it."
          guard-label="Unlock guard (Python expression)"
          guard-help="Optional sandboxed Python condition that must also be True to unlock this special."
        />
        <UiField label="Unlock message" hint="Optional.">
          <UiInput v-model="draft.unlock_text" placeholder="e.g. The relic hums as ancient knowledge floods your mind." />
        </UiField>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <UiField label="Legacy trigger">
            <UiSelect :model-value="draft.unlock_condition_type ?? ''" :options="LEGACY_UNLOCK_OPTIONS" @update:model-value="setLegacyUnlock" />
          </UiField>
          <UiField v-if="draft.unlock_condition_type" label="Item ID">
            <UiInput v-model="draft.unlock_condition_target" mono placeholder="ITEM_ID" />
          </UiField>
        </div>
      </template>
    </div>

    <!-- Success / failure scripting -->
    <UiDisclosure v-model:open="showScripts" label="Scripts & triggers" hint="success and failure" class="md:col-span-2">
      <div v-if="showScripts" class="grid grid-cols-1 gap-6 pt-3 lg:grid-cols-2">
        <TriggerScriptField
          :script="draft.on_success_script ?? ''"
          :text="draft.on_success_text ?? ''"
          label="On success"
          help="Runs when the success roll succeeds. `special` holds id, name, caster, target, success, crit, fumble, roll and dc."
          context="special_action"
          min-height="90px"
          @update:script="(v: string) => (draft.on_success_script = v)"
          @update:text="(v: string) => (draft.on_success_text = v)"
        />
        <TriggerScriptField
          :script="draft.on_failure_script ?? ''"
          :text="draft.on_failure_text ?? ''"
          label="On failure"
          help="Runs when the success roll fails. The same `special` dict is available."
          context="special_action"
          min-height="90px"
          @update:script="(v: string) => (draft.on_failure_script = v)"
          @update:text="(v: string) => (draft.on_failure_text = v)"
        />
      </div>
    </UiDisclosure>
  </div>
</template>
