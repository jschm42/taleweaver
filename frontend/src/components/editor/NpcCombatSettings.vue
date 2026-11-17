<script setup lang="ts">
import { ref, watch } from 'vue'
import { Save } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiRange from '@/components/ui/UiRange.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import type { SpecialAttack } from '@/types'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import SpecialAttacksEditor from '@/components/editor/SpecialAttacksEditor.vue'
import NpcCombatProfile from '@/components/editor/NpcCombatProfile.vue'
import { specialAttackService, type NpcAssistMode } from '@/services/specialAttackService'
import { useEntitySubform } from '@/components/editor/entity/entitySubforms'

type NpcLike = {
  id: string
  name: string
  stat_modifier_strength?: number | null
  stat_modifier_dexterity?: number | null
  stat_modifier_intelligence?: number | null
  stat_modifier_wisdom?: number | null
  stat_modifier_charisma?: number | null
  stat_modifier_armor_class?: number | null
  metadata_json?: {
    main_attack?: Record<string, any> | null
    equipped_weapon_id?: string | null
    equipped_armor_id?: string | null
    attack_mode?: string
    attack_trigger?: HardRule | null
    special_chance?: number
    combat_group?: string | null
    assist_mode?: NpcAssistMode | null
    special_actions?: SpecialAttack[]
  } | null
}

const props = defineProps<{
  adventureId: string
  npc: NpcLike
  referenceOptions?: Array<{ id: string; name?: string; type?: string }>
}>()

const emit = defineEmits<{
  saved: []
}>()

const attackOnSight = ref(false)
const trigger = ref<HardRule>({})
const specialChance = ref(40)
const combatGroup = ref('')
const assistMode = ref<NpcAssistMode | ''>('')

const ASSIST_OPTIONS: Array<{ value: NpcAssistMode | ''; label: string }> = [
  { value: '', label: 'Automatic (group members if a group is set, otherwise never)' },
  { value: 'GROUP', label: 'When a member of its group fights' },
  { value: 'ANYONE', label: 'In every fight in its scene' },
  { value: 'NEVER', label: 'Never (bystander, only when attacked itself)' },
]
const saving = ref(false)
const note = ref('')
const error = ref('')

function behaviourPayload() {
  const hasRule = Object.values(trigger.value).some((v) => !!String(v ?? '').trim())
  return {
    attack_mode: attackOnSight.value ? 'ATTACK_ON_SIGHT' : 'PASSIVE',
    attack_trigger: hasRule ? trigger.value : null,
    special_chance: specialChance.value,
    combat_group: combatGroup.value.trim() || null,
    assist_mode: assistMode.value || null,
  } as const
}

// Last loaded state, to tell whether the settings changed.
const loaded = ref('')

watch(() => [props.npc.id, JSON.stringify(props.npc.metadata_json ?? {})], () => {
  const meta = props.npc.metadata_json ?? {}
  attackOnSight.value = meta.attack_mode === 'ATTACK_ON_SIGHT'
  trigger.value = { ...(meta.attack_trigger ?? {}) }
  specialChance.value = typeof meta.special_chance === 'number' ? meta.special_chance : 40
  combatGroup.value = meta.combat_group ?? ''
  assistMode.value = meta.assist_mode ?? ''
  loaded.value = JSON.stringify(behaviourPayload())
}, { immediate: true })

async function persist(): Promise<void> {
  await specialAttackService.saveNpcCombat(props.adventureId, props.npc.id, behaviourPayload())
  loaded.value = JSON.stringify(behaviourPayload())
}

// Inside the entity form, "Save changes" saves these settings; elsewhere the own button does.
const embedded = useEntitySubform({
  label: 'Aggression',
  isDirty: () => JSON.stringify(behaviourPayload()) !== loaded.value,
  error: () => null,
  save: persist,
})

async function saveBehaviour(): Promise<void> {
  saving.value = true
  note.value = ''
  error.value = ''
  try {
    await persist()
    note.value = 'Saved.'
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-8">
    <UiSection title="Aggression" description="When this character starts or joins a fight.">
      <UiToggle
        v-model="attackOnSight"
        label="Attack on sight"
        description="Starts a fight as soon as the protagonist enters its scene."
      />

      <HardRuleTriggersEditor
        v-model="trigger"
        :reference-options="referenceOptions"
        title="Attack trigger"
        description="Optional: attacks once when all conditions are met while the protagonist is in its scene, e.g. when a certain item is picked up."
        guard-label="Attack guard (Python expression)"
        guard-help="Optional sandboxed Python condition, e.g. tw.player.has_item('IDOL') and not tw.vars.get('bribed_guard')."
        item-hint="Protagonist holds item X"
        scene-hint="Protagonist has reached scene X"
        npc-hint="Protagonist has defeated NPC X"
      />

      <div class="grid gap-4 sm:grid-cols-2">
        <UiField label="Combat group" hint="Characters of one group fight together.">
          <UiInput
            :model-value="combatGroup"
            maxlength="64"
            class="uppercase placeholder:normal-case" mono
            placeholder="e.g. BANDITS"
            @update:model-value="(value) => (combatGroup = String(value ?? ''))"
          />
        </UiField>
        <UiField label="Joins a fight" hint="Bystanders only fight when attacked themselves.">
          <UiSelect
            :model-value="assistMode"
            :options="ASSIST_OPTIONS"
            @update:model-value="(value) => (assistMode = (value || '') as NpcAssistMode | '')"
          />
        </UiField>
      </div>

      <UiField
        label="Special attack chance per turn"
        hint="How often it picks a special attack instead of a weapon attack. Badly hurt characters prefer healing."
      >
        <UiRange v-model="specialChance" :min="0" :max="100" :step="5" unit="%" />
      </UiField>

      <div v-if="!embedded" class="flex items-center gap-3">
        <UiButton :icon="Save" :loading="saving" @click="saveBehaviour">Save aggression</UiButton>
        <span v-if="note" class="wb-hint !text-wb-accent-text" role="status">{{ note }}</span>
        <span v-if="error" class="wb-hint !text-wb-danger-text" role="alert">{{ error }}</span>
      </div>
    </UiSection>

    <div class="border-t border-wb-line pt-6">
      <NpcCombatProfile :adventure-id="adventureId" :npc="npc" @saved="emit('saved')" />
    </div>

    <div class="border-t border-wb-line pt-6">
      <SpecialAttacksEditor
        :adventure-id="adventureId"
        target-type="npc"
        :target-id="npc.id"
        :owner-name="npc.name"
        :attacks="npc.metadata_json?.special_actions ?? []"
        :reference-options="referenceOptions"
        @saved="emit('saved')"
      />
    </div>
  </div>
</template>
