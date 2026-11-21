<script setup lang="ts">
/** Story idea, title and (advanced) builder mode and language of a new adventure. */
import { computed, ref } from 'vue'
import { FileUp, Sparkles } from 'lucide-vue-next'
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import { TITLE_MAX_LENGTH } from '@/composables/createAdventure/createAdventureForm'
import { STORY_IDEA_MAX_LENGTH } from '@/constants/storyIdeaLimits'
import BlueprintSyntaxHelp from '@/components/create-adventure/BlueprintSyntaxHelp.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInfoPopover from '@/components/ui/UiInfoPopover.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiRadioCards from '@/components/ui/UiRadioCards.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const { form, mode, isSuggesting, hasLlmConfig, suggestStoryIdea } = useCreateAdventureContext()
const fileInput = ref<HTMLInputElement | null>(null)

const LANGUAGES = [
  { value: '', label: 'Default (English)' },
  { value: 'German', label: 'Deutsch' },
  { value: 'English', label: 'English' },
  { value: 'French', label: 'Français' },
  { value: 'Spanish', label: 'Español' },
  { value: 'Italian', label: 'Italiano' },
  { value: 'Japanese', label: 'Japanese' },
  { value: 'Chinese', label: 'Chinese' },
  { value: 'Russian', label: 'Russian' },
  { value: 'Portuguese', label: 'Portuguese' },
]

const STRICTNESS = [
  { value: 'creative' as const, label: 'Creative expansion', description: 'Builds on your idea and fills the gaps freely.' },
  { value: 'strict' as const, label: 'Strict adherence', description: 'Follows your blueprint sections without inventing extra places.' },
]

const ideaError = computed(() => {
  const over = form.value.storyIdea.length - STORY_IDEA_MAX_LENGTH
  return over > 0 ? `Too long: shorten by ${over.toLocaleString('en-US')} characters.` : null
})

async function loadFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const content = await file.text()
  const heading = content.match(/^\s*#\s+([^\n#]+)$/m)
  if (!form.value.title.trim() && heading && !heading[1].includes(':')) {
    form.value.title = heading[1].trim().slice(0, TITLE_MAX_LENGTH)
  }
  form.value.storyIdea = content
}
</script>

<template>
  <UiCard title="Story idea" description="Describe the world, the hero or the conflict. A few sentences are enough.">
    <template #actions>
      <UiButton size="sm" variant="ghost" :icon="FileUp" @click="fileInput?.click()">Load .md</UiButton>
      <input ref="fileInput" type="file" accept=".md,.markdown,.txt" class="hidden" @change="loadFile" />
      <UiButton
        size="sm"
        variant="ai"
        :icon="Sparkles"
        :loading="isSuggesting"
        :disabled="!hasLlmConfig"
        @click="suggestStoryIdea"
      >
        Suggest an idea
      </UiButton>
    </template>
    <div class="space-y-4">
      <UiField
        label="Story idea"
        :count="form.storyIdea.length"
        :max-length="STORY_IDEA_MAX_LENGTH"
        :error="ideaError"
        hint="Optional blueprint headings pin scenes, characters and chapters."
      >
        <UiTextarea
          v-model="form.storyIdea"
          :rows="6"
          :max-rows="20"
          :invalid="!!ideaError"
          placeholder="e.g. A forgotten observatory buried beneath a glacier. Its ancient astrolabe has started sending coordinates to the stars…"
        />
      </UiField>
      <div class="flex items-center gap-1.5">
        <span class="wb-hint">Blueprint syntax</span>
        <UiInfoPopover title="Blueprint syntax" wide>
          <BlueprintSyntaxHelp />
        </UiInfoPopover>
      </div>
      <UiField
        label="Title"
        hint="Optional. Left empty, the first words of the idea are used."
        :count="form.title.length"
        :max-length="TITLE_MAX_LENGTH"
      >
        <UiInput v-model="form.title" :maxlength="TITLE_MAX_LENGTH" placeholder="e.g. The Frozen Observatory" />
      </UiField>
      <template v-if="mode === 'advanced'">
        <UiField label="Builder mode">
          <UiRadioCards v-model="form.generation_strictness" :options="STRICTNESS" label="Builder mode" />
        </UiField>
        <UiField label="Language" hint="Names, descriptions and the story are written in this language.">
          <UiSelect v-model="form.language" :options="LANGUAGES" class="sm:max-w-xs" />
        </UiField>
      </template>
    </div>
  </UiCard>
</template>
