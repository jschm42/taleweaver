<script setup lang="ts">
import { computed } from 'vue'
import { Check, Sparkles } from 'lucide-vue-next'
import type { EntityReference } from '@/composables/editor/useEntityReferences'
import { QUEST_DESCRIPTION_MAX, QUEST_TITLE_MAX, type Quest } from '@/composables/editor/useSideQuests'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'

/** Creates or edits one side quest; "Save quest" stores the quest list. */
const open = defineModel<boolean>('open', { required: true })
const quest = defineModel<Quest>('quest', { required: true })

const props = defineProps<{
  isNew: boolean
  saving: boolean
  references: EntityReference[]
  textReferences: Array<{ id: string; name?: string; imageUrl?: string | null }>
  generatingQuest: boolean
  generatingDescription: boolean
}>()

const emit = defineEmits<{ save: []; 'draft-quest': []; 'draft-description': [] }>()

const completion = computed<HardRule>({
  get: () => ({
    required_item_id: quest.value.required_item_id,
    required_scene_id: quest.value.required_scene_id,
    required_defeated_npc_id: quest.value.required_defeated_npc_id,
    guard_expression: quest.value.guard_expression,
  }),
  set: (rule) => {
    quest.value.required_item_id = rule.required_item_id || ''
    quest.value.required_scene_id = rule.required_scene_id || ''
    quest.value.required_defeated_npc_id = rule.required_defeated_npc_id || ''
    quest.value.guard_expression = rule.guard_expression || ''
  },
})

const title = computed(() => String(quest.value.title || ''))
const description = computed(() => String(quest.value.description || ''))
const canSave = computed(
  () =>
    Boolean(title.value.trim() && description.value.trim()) &&
    title.value.length <= QUEST_TITLE_MAX &&
    description.value.length <= QUEST_DESCRIPTION_MAX,
)

function toReward(value: string | number | null): number {
  return Math.max(0, Math.min(9999, Number(value) || 0))
}
</script>

<template>
  <UiModal
    v-model:open="open"
    :title="isNew ? 'New side quest' : `Edit side quest: ${quest.title || quest.id}`"
    :description="isNew ? 'An optional goal that rewards extra XP.' : `ID ${quest.id}`"
    size="xl"
    :persistent="saving"
  >
    <div class="space-y-5">
      <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_120px]">
        <UiField label="Title" required :count="title.length" :max-length="QUEST_TITLE_MAX">
          <UiInput v-model="quest.title" :maxlength="QUEST_TITLE_MAX" placeholder="e.g. Find the Lost Key" />
        </UiField>
        <UiField label="XP reward">
          <UiInput type="number" min="0" max="9999" :model-value="quest.exp_reward" @update:model-value="(v) => (quest.exp_reward = toReward(v))" />
        </UiField>
      </div>
      <UiButton v-if="isNew" variant="ai" size="sm" :icon="Sparkles" :loading="generatingQuest" @click="emit('draft-quest')">
        Draft title and description
      </UiButton>

      <div class="space-y-2">
        <UiField
          label="Description"
          required
          hint="What the protagonist needs to do. Reference entities with ##ID."
          :count="description.length"
          :max-length="QUEST_DESCRIPTION_MAX"
        >
          <ReferenceTextarea
            v-model="quest.description"
            :maxlength="QUEST_DESCRIPTION_MAX"
            :rows="3"
            :options="textReferences"
            placeholder="Explain what the protagonist needs to do..."
          />
        </UiField>
        <div class="flex justify-end">
          <UiButton
            variant="ai"
            size="sm"
            :icon="Sparkles"
            :loading="generatingDescription"
            :disabled="!title.trim()"
            @click="emit('draft-description')"
          >
            {{ description.trim() ? 'Regenerate description' : 'Generate description' }}
          </UiButton>
        </div>
      </div>

      <UiField label="Goal (soft rule)" hint="Judged by the Game Master to decide when the quest is done.">
        <UiInput v-model="quest.goal" placeholder="e.g. Return the merchant's lost ledger to him in the marketplace." />
      </UiField>

      <HardRuleTriggersEditor
        v-model="completion"
        :reference-options="props.references"
        title="Completion triggers (hard rules)"
        description="Checked by the engine: the quest completes when all configured conditions are met."
        guard-label="Completion guard (Python expression)"
        guard-help="Optional condition; the quest completes only when it is True."
        item-hint="Protagonist holds item X"
        scene-hint="Protagonist reaches scene X"
        npc-hint="Protagonist defeats character X"
      />
    </div>
    <template #footer>
      <UiButton :disabled="saving" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :icon="Check" :loading="saving" :disabled="!canSave" @click="emit('save')">
        {{ isNew ? 'Create quest' : 'Save quest' }}
      </UiButton>
    </template>
  </UiModal>
</template>
