<script setup lang="ts">
/** Edits one narrator persona in a copy; "Apply" hands it back to the page's draft. */
import { computed, ref, watch } from 'vue'
import { VOICE_INSTRUCTION_MAX, VOICE_SAMPLE_MAX, type NarratorVoice } from '@/services/narratorVoiceService'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const props = defineProps<{ open: boolean; voice: NarratorVoice | null; isNew: boolean }>()
const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'apply', voice: NarratorVoice): void
}>()

const editing = ref<NarratorVoice>({ id: '', name: '', description: '', instruction: '', sample: '' })

watch(
  () => [props.open, props.voice] as const,
  ([open, voice]) => {
    if (open) editing.value = { id: '', name: '', description: '', instruction: '', sample: '', ...(voice || {}) }
  },
  { immediate: true },
)

const canApply = computed(() => Boolean(editing.value.name.trim() && editing.value.instruction.trim()))

function apply(): void {
  if (!canApply.value) return
  emit('apply', { ...editing.value })
  emit('update:open', false)
}
</script>

<template>
  <UiModal
    :open="open"
    :title="isNew ? 'Add persona' : 'Edit persona'"
    description="Changes are kept in the page and saved with the save bar."
    size="lg"
    @update:open="(value) => emit('update:open', value)"
  >
    <form class="space-y-4" @submit.prevent="apply">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <UiField label="Name" required>
          <UiInput v-model="editing.name" maxlength="80" placeholder="e.g. Hardboiled Noir Detective" />
        </UiField>
        <UiField label="Short description">
          <UiInput v-model="editing.description" maxlength="300" placeholder="Genre and character of the persona" />
        </UiField>
      </div>
      <UiField
        label="Instruction for the Game Master"
        required
        :count="editing.instruction.length"
        :max-length="VOICE_INSTRUCTION_MAX"
      >
        <UiTextarea v-model="editing.instruction" :maxlength="VOICE_INSTRUCTION_MAX" :rows="5" placeholder="Narrate like … Use … Never …" />
      </UiField>
      <UiField
        label="Style sample"
        hint="One or two sentences in this voice. The Game Master copies the style, not the content."
        :count="(editing.sample || '').length"
        :max-length="VOICE_SAMPLE_MAX"
      >
        <UiTextarea v-model="editing.sample" :maxlength="VOICE_SAMPLE_MAX" :rows="3" />
      </UiField>
    </form>
    <template #footer>
      <UiButton variant="ghost" @click="emit('update:open', false)">Cancel</UiButton>
      <UiButton variant="primary" :disabled="!canApply" @click="apply">Apply</UiButton>
    </template>
  </UiModal>
</template>
