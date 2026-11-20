<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import UiField from '@/components/ui/UiField.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const ef = useEntityFormContext()
</script>

<template>
  <UiField
    v-if="ef.type === 'npc'"
    label="Condition notes for the Game Master"
    hint="Current state the narration should reflect, e.g. badly hurt or angry at Joe."
    :count="(ef.localForm.notes || '').length"
    :max-length="500"
    class="border-t border-wb-line pt-6"
  >
    <UiTextarea v-model="ef.localForm.notes" :rows="2" maxlength="500" placeholder="e.g. is badly hurt, holds a grudge against Joe…" />
  </UiField>
</template>
