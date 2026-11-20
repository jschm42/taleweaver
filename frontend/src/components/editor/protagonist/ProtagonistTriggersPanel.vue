<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Save } from 'lucide-vue-next'
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiSection from '@/components/ui/UiSection.vue'
import type { ProtagonistData } from './protagonistTypes'

/** Scripts and narration cues that run when the protagonist's HP or status effects change. */
const props = defineProps<{ protagonist: ProtagonistData; isSaving: boolean }>()
const emit = defineEmits<{ 'save-fields': [changes: Record<string, string>] }>()

const FIELDS = ['on_hp_change_script', 'on_hp_change_text', 'on_status_change_script', 'on_status_change_text'] as const
type TriggerField = (typeof FIELDS)[number]

const draft = reactive<Record<TriggerField, string>>({
  on_hp_change_script: '',
  on_hp_change_text: '',
  on_status_change_script: '',
  on_status_change_text: '',
})

watch(
  () => props.protagonist,
  (p) => {
    for (const field of FIELDS) draft[field] = p[field] || ''
  },
  { immediate: true, deep: true },
)

const changed = computed(() => FIELDS.filter((field) => draft[field] !== (props.protagonist[field] || '')))

function save(): void {
  emit('save-fields', Object.fromEntries(changed.value.map((field) => [field, draft[field]])))
}
</script>

<template>
  <div class="space-y-8">
    <p class="wb-body text-wb-muted">Scripts and narration cues that run when the protagonist's state changes. Leave empty when not needed.</p>

    <UiSection title="HP change" description="Runs when the protagonist's HP changes, e.g. to start a low-health event.">
      <TriggerScriptField
        v-model:script="draft.on_hp_change_script"
        v-model:text="draft.on_hp_change_text"
        label="On HP change"
        help="Executed immediately when the protagonist's HP changes (e.g. check if HP <= 0)."
        context="protagonist_hp_change"
        min-height="120px"
        text-placeholder="e.g. Your vision flashes red as agonizing pain shoots through your body."
      />
    </UiSection>

    <UiSection
      title="Status change"
      description="Runs when status effects or conditions change."
      class="border-t border-wb-line pt-6"
    >
      <TriggerScriptField
        v-model:script="draft.on_status_change_script"
        v-model:text="draft.on_status_change_text"
        label="On status change"
        help="Executed immediately when the protagonist's status effects or conditions change."
        context="protagonist_status_change"
        min-height="120px"
        text-placeholder="e.g. A tingling sensation spreads across your skin as your condition shifts."
      />
    </UiSection>

    <div class="flex items-center gap-3 border-t border-wb-line pt-4">
      <UiButton variant="primary" :icon="Save" :loading="isSaving" :disabled="changed.length === 0" @click="save">
        Save triggers
      </UiButton>
      <span v-if="changed.length" class="wb-hint !text-wb-warn-text">Unsaved changes</span>
    </div>
  </div>
</template>
