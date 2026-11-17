<script setup lang="ts">
import { cloneValue, useDraft } from '@/composables/useDraft'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps<{
  gameForm: any
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: any): void
}>()

const { draft, isDirty, changedCount, reset } = useDraft(() => props.gameForm)

const WHISPER_MODELS = [
  { value: 'tiny', label: 'Tiny (default, fastest)' },
  { value: 'base', label: 'Base' },
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large (slowest)' },
]
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Speech-to-text" description="Speech recognition for voice input in the game." />

    <UiCard title="Recognition">
      <template #actions>
        <UiBadge tone="accent">faster-whisper (local)</UiBadge>
      </template>
      <div class="space-y-5">
        <p class="wb-body text-wb-muted">Voice input runs on this server with Whisper; no other provider is supported yet.</p>
        <UiField label="Whisper model" hint="Larger models recognize speech better but need more CPU and memory.">
          <UiSelect v-model="draft.whisper_model" :options="WHISPER_MODELS" class="max-w-xs" />
        </UiField>
      </div>
    </UiCard>

    <UiSaveBar
      :dirty="isDirty"
      :count="changedCount"
      :saving="isSubmitting"
      @save="emit('save', cloneValue(draft))"
      @discard="reset"
    />
  </div>
</template>
