<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EditorIdInput from '@/components/editor/EditorIdInput.vue'
import { MAX_EDITOR_ID_LENGTH } from '@/utils/editor_utils'

const ef = useEntityFormContext()
</script>

<template>
  <!-- Editable ID (create mode or scene/npc/object edit mode) -->
  <div v-if="ef.props.isCreateEntityMode || ['npc', 'object', 'scene'].includes(ef.type)" class="space-y-2">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">
      {{ ef.type === 'scene' ? 'Scene ID' : 'Entity ID' }} <span class="text-red-400">*</span>
    </label>
    <EditorIdInput
      v-model="ef.localForm.entity_id"
      :prefix="ef.entityIdPrefix"
      :source-name="ef.localForm.name"
      :taken-ids="ef.takenEntityIds"
      :original-id="ef.props.isCreateEntityMode ? null : ef.originalEntityId"
      :max-length="MAX_EDITOR_ID_LENGTH"
      :required="true"
      :placeholder="`${ef.entityIdPrefix}001`"
      :aria-label="ef.type === 'scene' ? 'Scene ID' : 'Entity ID'"
    />
    <p class="text-[10px] text-slate-500 uppercase tracking-wider">
      Unique identifier. Uppercase A-Z, digits 0-9, and underscores only (max 20 chars).
    </p>
  </div>
</template>
