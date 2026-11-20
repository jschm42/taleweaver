<script setup lang="ts">
import { computed } from 'vue'
import type { Chapter, ChapterReference, ProgressionMode } from '@/composables/editor/useChapters'
import EditorIdInput from '@/components/editor/EditorIdInput.vue'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import { EDITOR_ID_PREFIXES, MAX_EDITOR_ID_LENGTH } from '@/utils/editor_utils'

/** General tab of a chapter: title, goal, completion rules, activation and party rules. */
const chapter = defineModel<Chapter>({ required: true })

const props = defineProps<{
  isNew: boolean
  mode: ProgressionMode
  takenIds: string[]
  references: ChapterReference[]
}>()

const sceneOptions = computed(() => [
  { value: '', label: 'None (activated by a script)' },
  ...props.references.filter((r) => r.type === 'SCENE').map((r) => ({ value: r.id, label: `${r.name} (${r.id})` })),
])

const completion = computed<HardRule>({
  get: () => ({
    required_item_id: chapter.value.required_item_id,
    required_scene_id: chapter.value.required_scene_id,
    required_defeated_npc_id: chapter.value.required_defeated_npc_id,
    guard_expression: chapter.value.guard_expression,
  }),
  set: (rule) => {
    chapter.value.required_item_id = rule.required_item_id || ''
    chapter.value.required_scene_id = rule.required_scene_id || ''
    chapter.value.required_defeated_npc_id = rule.required_defeated_npc_id || ''
    chapter.value.guard_expression = rule.guard_expression || ''
  },
})

function toReward(value: string | number | null): number {
  return Math.max(0, Math.min(10000, Number(value) || 0))
}
</script>

<template>
  <div class="space-y-6">
    <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_120px]">
      <UiField label="Title" required>
        <UiInput v-model="chapter.title" maxlength="80" placeholder="e.g. The Escape From Cell Block C" />
      </UiField>
      <UiField label="XP reward">
        <UiInput
          type="number"
          min="0"
          max="10000"
          :model-value="chapter.exp_reward"
          @update:model-value="(v) => (chapter.exp_reward = toReward(v))"
        />
      </UiField>
    </div>
    <UiField label="ID" required :hint="isNew ? 'Scripts refer to the chapter by this ID.' : 'The ID cannot change after creation.'">
      <EditorIdInput
        v-model="chapter.id"
        :prefix="EDITOR_ID_PREFIXES.SEQUENCE"
        :source-name="chapter.title"
        :taken-ids="takenIds"
        :original-id="isNew ? null : chapter.id"
        :disabled="!isNew"
        :max-length="MAX_EDITOR_ID_LENGTH"
        :required="true"
        placeholder="SEQ_CELL_ESCAPE"
        aria-label="Chapter ID"
      />
    </UiField>
    <UiField label="Description" hint="What happens in this chapter; story backdrop for the Game Master.">
      <UiTextarea v-model="chapter.description" :rows="3" />
    </UiField>
    <UiField label="Game Master walkthrough" hint="Solution steps for this chapter.">
      <UiTextarea v-model="chapter.walkthrough" :rows="2" />
    </UiField>

    <div class="space-y-4 border-t border-wb-line pt-5">
      <h3 class="wb-subheading">Completion</h3>
      <UiField label="End condition (soft rule)" hint="Judged by the Game Master to decide when the chapter is done.">
        <UiInput v-model="chapter.end_condition" placeholder="e.g. Player convinces the gatekeeper or solves the courtyard riddle." />
      </UiField>
      <HardRuleTriggersEditor
        v-model="completion"
        :reference-options="references"
        title="Completion triggers (hard rules)"
        description="Checked by the engine: the chapter completes when all configured conditions are met."
        guard-label="Completion guard (Python expression)"
        guard-help="Optional condition checked in addition to the triggers; the chapter completes only when it is True."
        item-hint="Protagonist holds item X"
        scene-hint="Protagonist reaches scene X"
        npc-hint="Protagonist defeats character X"
      />
    </div>

    <div class="space-y-4 border-t border-wb-line pt-5">
      <h3 class="wb-subheading">Activation and party</h3>
      <UiField
        label="Activation scene"
        :hint="mode === 'dynamic' ? 'Activates the chapter when the protagonist enters this scene.' : 'Only used in dynamic mode.'"
      >
        <UiSelect v-model="chapter.activation_scene_id" :options="sceneOptions" />
      </UiField>
      <UiCheckbox
        v-model="chapter.companions_allowed"
        label="Companions follow in this chapter"
        description="Off for a solo chapter: the companion stays behind when the protagonist changes scenes."
      />
      <UiCheckbox
        v-model="chapter.respawn_allowed"
        label="Respawn allowed in this chapter"
        description="Only matters when the adventure respawns at 0 HP (Overview → Outcome). Off: 0 HP ends the adventure here."
      />
    </div>
  </div>
</template>
