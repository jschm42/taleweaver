<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Plus, RotateCcw, ScrollText, Trash2 } from 'lucide-vue-next'
import {
  narratorVoiceService,
  VOICE_INSTRUCTION_MAX,
  VOICE_SAMPLE_MAX,
  type NarratorVoice,
} from '@/services/narratorVoiceService'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const toast = useToast()
const saved = ref<NarratorVoice[]>([])
const defaults = ref<NarratorVoice[]>([])
const isLoading = ref(true)
const loadError = ref('')

const { draft: voices, isDirty, changedCount, isSaving, reset, commit } = useDraft(() => saved.value)

const copy = (list: NarratorVoice[]) => list.map((voice) => ({ ...voice }))

onMounted(async () => {
  try {
    const catalog = await narratorVoiceService.load()
    saved.value = copy(catalog.items)
    defaults.value = catalog.defaults
  } catch (err) {
    loadError.value = (err as Error).message
  } finally {
    isLoading.value = false
  }
})

const addVoice = () => {
  voices.value.push({ id: '', name: '', description: '', instruction: '', sample: '' })
}

const removeVoice = (index: number) => {
  voices.value.splice(index, 1)
}

const restoreDefaults = () => {
  voices.value = copy(defaults.value)
}

const save = async () => {
  try {
    let result: NarratorVoice[] = []
    await commit(async (list) => {
      const complete = list.filter((voice) => voice.name.trim() && voice.instruction.trim())
      result = copy(await narratorVoiceService.save(complete))
    })
    saved.value = result
    toast.success('Narrator personas saved.')
  } catch (err) {
    toast.error((err as Error).message)
  }
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      title="Narrator personas"
      description="How the Game Master words the narration. Authors pick one per adventure in the editor's Tone page."
    >
      <template #actions>
        <UiButton :icon="RotateCcw" title="Replace the list with the built-in personas (saved only when you save)" @click="restoreDefaults">
          Restore defaults
        </UiButton>
        <UiButton variant="primary" :icon="Plus" @click="addVoice">Add persona</UiButton>
      </template>
    </PageHeader>

    <div v-if="isLoading" class="flex justify-center py-10"><UiSpinner label="Loading personas" /></div>
    <p v-else-if="loadError" class="wb-body text-wb-danger-text" role="alert">{{ loadError }}</p>

    <template v-else>
      <UiEmptyState
        v-if="!voices.length"
        :icon="ScrollText"
        title="No personas"
        description="Saving an empty list restores the built-in personas."
      >
        <template #action>
          <UiButton variant="primary" :icon="Plus" @click="addVoice">Add persona</UiButton>
        </template>
      </UiEmptyState>

      <UiCard v-for="(voice, index) in voices" :key="index" :title="voice.name || 'New persona'" :description="voice.description">
        <template #actions>
          <UiIconButton :icon="Trash2" :label="`Remove ${voice.name || 'this persona'}`" variant="danger" size="sm" @click="removeVoice(index)" />
        </template>
        <div class="space-y-4">
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <UiField label="Name" required>
              <UiInput v-model="voice.name" maxlength="80" placeholder="e.g. Hardboiled Noir Detective" />
            </UiField>
            <UiField label="Short description">
              <UiInput v-model="voice.description" maxlength="300" placeholder="Genre and character of the persona" />
            </UiField>
          </div>
          <UiField
            label="Instruction for the Game Master"
            required
            hint="Personas without a name or instruction are skipped when saving."
            :count="voice.instruction.length"
            :max-length="VOICE_INSTRUCTION_MAX"
          >
            <UiTextarea v-model="voice.instruction" :maxlength="VOICE_INSTRUCTION_MAX" :rows="3" placeholder="Narrate like … Use … Never …" />
          </UiField>
          <UiField
            label="Style sample"
            hint="One or two sentences in this voice. The Game Master copies the style, not the content."
            :count="(voice.sample || '').length"
            :max-length="VOICE_SAMPLE_MAX"
          >
            <UiTextarea v-model="voice.sample" :maxlength="VOICE_SAMPLE_MAX" :rows="2" />
          </UiField>
        </div>
      </UiCard>
    </template>

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
