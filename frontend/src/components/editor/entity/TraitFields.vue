<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import { CONTROL_TEXTAREA_CLASS } from '@/components/ui/fieldContext'

/** Goal and character traits of a character or the protagonist, each with AI generation. */
defineProps<{
  goalLabel: string
  goalPlaceholder: string
  characterLabel: string
  characterPlaceholder: string
}>()

const ef = useEntityFormContext()
</script>

<template>
  <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
    <UiField :label="goalLabel" :count="(ef.localForm.goal || '').length" :max-length="200">
      <div class="space-y-2">
        <ReferenceTextarea
          v-model="ef.localForm.goal"
          :maxlength="200"
          :rows="2"
          :options="ef.props.referenceOptions || []"
          :class-name="CONTROL_TEXTAREA_CLASS"
          :placeholder="goalPlaceholder"
        />
        <UiButton
          v-if="ef.localForm.description"
          variant="ai"
          size="sm"
          :icon="Sparkles"
          :loading="ef.isGenerating['goal']"
          @click="ef.handleGenerateTraits('goal')"
        >
          Generate goal
        </UiButton>
      </div>
    </UiField>
    <UiField :label="characterLabel" :count="(ef.localForm.character || '').length" :max-length="200">
      <div class="space-y-2">
        <ReferenceTextarea
          v-model="ef.localForm.character"
          :maxlength="200"
          :rows="2"
          :options="ef.props.referenceOptions || []"
          :class-name="CONTROL_TEXTAREA_CLASS"
          :placeholder="characterPlaceholder"
        />
        <UiButton
          v-if="ef.localForm.description"
          variant="ai"
          size="sm"
          :icon="Sparkles"
          :loading="ef.isGenerating['character']"
          @click="ef.handleGenerateTraits('character')"
        >
          Generate traits
        </UiButton>
      </div>
    </UiField>
  </div>
</template>
