<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import AppearanceField from '@/components/editor/AppearanceField.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import { CONTROL_TEXTAREA_CLASS } from '@/components/ui/fieldContext'

const ef = useEntityFormContext()
</script>

<template>
  <div v-if="!ef.isRecipe" class="space-y-5 border-t border-wb-line pt-6">
    <UiField
      :label="['npc', 'protagonist'].includes(ef.type) ? 'Biography' : 'Description'"
      required
      :count="(ef.localForm.description || '').length"
      :max-length="1000"
    >
      <div class="space-y-2">
        <ReferenceTextarea
          v-model="ef.localForm.description"
          :maxlength="1000"
          :rows="ef.type === 'object' ? 3 : 5"
          :options="ef.props.referenceOptions || []"
          :class-name="CONTROL_TEXTAREA_CLASS"
        />
        <UiButton
          v-if="['npc', 'protagonist'].includes(ef.type) && ef.localForm.name && ef.localForm.goal && ef.localForm.character"
          variant="ai"
          size="sm"
          :icon="Sparkles"
          :loading="ef.isGenerating['biography']"
          title="Writes a biography from name, goal and traits"
          @click="ef.handleGenerateBiography"
        >
          Generate biography
        </UiButton>
        <UiButton
          v-if="ef.type === 'object' && ef.localForm.name"
          variant="ai"
          size="sm"
          :icon="Sparkles"
          :loading="ef.isGenerating['description']"
          @click="ef.handleGenerateDescription"
        >
          Generate description
        </UiButton>
      </div>
    </UiField>

    <AppearanceField
      v-if="['cover', 'protagonist', 'npc', 'object'].includes(ef.type) && !ef.isRecipe"
      v-model="ef.localForm.appearance"
      :target-type="ef.type"
    />
  </div>
</template>
