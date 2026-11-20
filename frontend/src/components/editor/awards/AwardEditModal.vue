<script setup lang="ts">
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'
import type { EntityReference } from '@/composables/editor/useEntityReferences'
import { AWARD_DESCRIPTION_MAX, AWARD_TITLE_MAX, type Award, type AwardTier } from '@/composables/editor/useAwards'
import EditorIdInput from '@/components/editor/EditorIdInput.vue'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import { EDITOR_ID_PREFIXES, MAX_EDITOR_ID_LENGTH } from '@/utils/editor_utils'

/** Creates or edits one award; "Save award" stores the award list. */
const open = defineModel<boolean>('open', { required: true })
const award = defineModel<Award>('award', { required: true })

defineProps<{
  isNew: boolean
  saving: boolean
  takenKeys: string[]
  references: EntityReference[]
  textReferences: Array<{ id: string; name?: string; imageUrl?: string | null }>
}>()

const emit = defineEmits<{ save: [] }>()

const TIERS = [
  { value: 'bronze' as AwardTier, label: 'Bronze' },
  { value: 'silver' as AwardTier, label: 'Silver' },
  { value: 'gold' as AwardTier, label: 'Gold' },
  { value: 'negative' as AwardTier, label: 'Negative' },
]

const tier = computed({
  get: (): AwardTier => (['silver', 'gold', 'negative'].includes(award.value.tier) ? award.value.tier : 'bronze'),
  set: (value: AwardTier) => {
    award.value.tier = value
  },
})

const grant = computed<HardRule>({
  get: () => ({
    required_item_id: award.value.required_item_id,
    required_scene_id: award.value.required_scene_id,
    required_defeated_npc_id: award.value.required_defeated_npc_id,
    guard_expression: award.value.guard_expression,
  }),
  set: (rule) => {
    award.value.required_item_id = rule.required_item_id || ''
    award.value.required_scene_id = rule.required_scene_id || ''
    award.value.required_defeated_npc_id = rule.required_defeated_npc_id || ''
    award.value.guard_expression = rule.guard_expression || ''
  },
})

const titleLength = computed(() => String(award.value.title || '').length)
const descriptionLength = computed(() => String(award.value.description || '').length)
const canSave = computed(
  () =>
    Boolean(String(award.value.title || '').trim() && String(award.value.description || '').trim()) &&
    titleLength.value <= AWARD_TITLE_MAX &&
    descriptionLength.value <= AWARD_DESCRIPTION_MAX,
)
</script>

<template>
  <UiModal
    v-model:open="open"
    :title="isNew ? 'New award' : `Edit award: ${award.title || award.key}`"
    description="An achievement players earn during the adventure."
    size="xl"
    :persistent="saving"
  >
    <div class="space-y-5">
      <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
        <UiField label="Title" required :count="titleLength" :max-length="AWARD_TITLE_MAX">
          <UiInput v-model="award.title" :maxlength="AWARD_TITLE_MAX" placeholder="e.g. Master of the Ruins" />
        </UiField>
        <div class="space-y-2">
          <p class="wb-label">Tier</p>
          <UiSegmented v-model="tier" :options="TIERS" label="Tier" />
        </div>
      </div>
      <UiField label="Key" required :hint="isNew ? 'Scripts grant the award by this key.' : 'The key cannot change after creation.'">
        <EditorIdInput
          v-model="award.key"
          :prefix="EDITOR_ID_PREFIXES.AWARD"
          :source-name="award.title"
          :taken-ids="takenKeys"
          :original-id="isNew ? null : award.key"
          :disabled="!isNew"
          :max-length="MAX_EDITOR_ID_LENGTH"
          :required="true"
          placeholder="AWD_MASTER_RUINS"
          aria-label="Award key"
        />
      </UiField>
      <UiField label="Description" required hint="Why the award is granted." :count="descriptionLength" :max-length="AWARD_DESCRIPTION_MAX">
        <ReferenceTextarea
          v-model="award.description"
          :maxlength="AWARD_DESCRIPTION_MAX"
          :rows="3"
          :options="textReferences"
          placeholder="Explain why this achievement is granted..."
        />
      </UiField>
      <UiField label="Requirement (soft rule)" hint="Judged by the Game Master to grant the award during play.">
        <ReferenceTextarea
          v-model="award.requirement"
          :rows="2"
          :options="textReferences"
          placeholder="e.g. Solve the riddle of the sphinx without using violence."
        />
      </UiField>
      <HardRuleTriggersEditor
        v-model="grant"
        :reference-options="references"
        title="Grant triggers (hard rules)"
        description="Checked by the engine: the award is granted when all configured conditions are met."
        guard-label="Grant guard (Python expression)"
        guard-help="Optional condition; the award is granted when it is True."
        item-hint="Protagonist holds item X"
        scene-hint="Protagonist reaches scene X"
        npc-hint="Protagonist defeats character X"
      />
    </div>
    <template #footer>
      <UiButton :disabled="saving" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :icon="Check" :loading="saving" :disabled="!canSave" @click="emit('save')">
        {{ isNew ? 'Create award' : 'Save award' }}
      </UiButton>
    </template>
  </UiModal>
</template>
