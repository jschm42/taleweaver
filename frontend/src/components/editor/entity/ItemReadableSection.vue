<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const ef = useEntityFormContext()

const FORMATS = [
  { value: 'DOCUMENT', label: 'Document' },
  { value: 'SCROLL', label: 'Scroll' },
  { value: 'BOOK', label: 'Book' },
  { value: 'SIGN', label: 'Sign' },
]

// Box from the Workbench tokens; font and color come from the in-game format preview.
const TEXT_BOX =
  'w-full rounded-md bg-wb-raised border border-wb-line-strong px-3 py-2 resize-y placeholder:text-wb-faint ' +
  'focus:outline-none focus:ring-2 focus:border-wb-accent focus:ring-wb-accent/40'
</script>

<template>
  <UiSection v-if="ef.currentItemType === 'READABLE'" title="Readable text" class="border-t border-wb-line pt-6">
    <UiField label="Format" hint="The preview below shows how it looks in the game." class="sm:max-w-xs">
      <UiSelect v-model="ef.localForm.text_log_format" :options="FORMATS" />
    </UiField>
    <UiField label="Text" :count="(ef.localForm.text_log_content || '').length" :max-length="1000">
      <div class="space-y-2">
        <ReferenceTextarea
          v-model="ef.localForm.text_log_content"
          :maxlength="1000"
          :rows="4"
          :options="ef.props.referenceOptions || []"
          :class-name="`${TEXT_BOX} ${ef.textLogPreviewClass}`"
          placeholder="The text the player reads."
        />
        <UiButton
          v-if="ef.localForm.name"
          variant="ai"
          size="sm"
          :icon="Sparkles"
          :loading="ef.isGenerating['text_log']"
          @click="ef.handleGenerateTextLogContent"
        >
          Generate text
        </UiButton>
      </div>
    </UiField>
  </UiSection>
</template>
