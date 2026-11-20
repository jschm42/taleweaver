<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EditorIdInput from '@/components/editor/EditorIdInput.vue'
import UiField from '@/components/ui/UiField.vue'
import { MAX_EDITOR_ID_LENGTH } from '@/utils/editor_utils'

const ef = useEntityFormContext()
</script>

<template>
  <UiField
    v-if="ef.props.isCreateEntityMode || ['npc', 'object', 'scene'].includes(ef.type)"
    :label="ef.type === 'scene' ? 'Scene ID' : 'ID'"
    required
    :hint="`Unique; A–Z, 0–9 and underscores, up to ${MAX_EDITOR_ID_LENGTH} characters.`"
  >
    <EditorIdInput
      v-model="ef.localForm.entity_id"
      :prefix="ef.entityIdPrefix"
      :source-name="ef.localForm.name"
      :taken-ids="ef.takenEntityIds"
      :original-id="ef.props.isCreateEntityMode ? null : ef.originalEntityId"
      :max-length="MAX_EDITOR_ID_LENGTH"
      :required="true"
      :placeholder="`${ef.entityIdPrefix}001`"
      :aria-label="ef.type === 'scene' ? 'Scene ID' : 'ID'"
    />
  </UiField>
</template>
