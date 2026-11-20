<script setup lang="ts">
import { ref } from 'vue'
import { formatObjectIds } from '@/utils/editor_utils'
import InlineEditableField from '@/components/editor/InlineEditableField.vue'
import NpcVoicePicker from '@/components/editor/NpcVoicePicker.vue'
import TalentsEditor from '@/components/editor/TalentsEditor.vue'
import type { TtsVoiceList } from '@/types'
import ProtagonistPortrait from './ProtagonistPortrait.vue'
import type { ProtagonistData, ReferenceOption } from './protagonistTypes'

/** Portrait, name, biography, voice, appearance and talents of the protagonist. Fields save on confirm. */
const props = defineProps<{
  protagonist: ProtagonistData
  isSavingText: boolean
  isGenerating: boolean
  visualsCacheVersion: number
  referenceOptions: ReferenceOption[]
  adventureId?: string
  voiceList?: TtsVoiceList | null
}>()

const emit = defineEmits<{
  'save-field': [field: string, value: unknown]
  'quick-regen': []
  'open-regen-dialog': []
  'open-upload-picker': []
  'download-asset': []
  'talents-saved': []
}>()

const activeEditId = ref<string | null>(null)

const TEXT_FIELDS = [
  { key: 'goal', label: 'Motivation', empty: 'No motivation set. Click to add details.' },
  { key: 'character', label: 'Traits', empty: 'No traits set. Click to add details.' },
] as const

function textOf(key: 'description' | 'goal' | 'character'): string {
  return props.protagonist[key] ?? ''
}
</script>

<template>
  <div class="flex flex-col gap-6 md:flex-row">
    <ProtagonistPortrait
      :protagonist="protagonist"
      :is-generating="isGenerating"
      :visuals-cache-version="visualsCacheVersion"
      @quick-regen="emit('quick-regen')"
      @open-regen-dialog="emit('open-regen-dialog')"
      @open-upload-picker="emit('open-upload-picker')"
      @download-asset="emit('download-asset')"
    />

    <div class="min-w-0 flex-grow space-y-5">
      <div class="space-y-1">
        <p class="wb-label">Name</p>
        <InlineEditableField
          :value="protagonist.name ?? ''"
          type="text"
          :maxlength="50"
          required
          :is-saving="isSavingText"
          edit-id="name"
          :active-edit-id="activeEditId"
          @save="emit('save-field', 'name', $event)"
          @start-edit="activeEditId = $event"
        >
          <template #default="{ value }">
            <span class="wb-subheading">{{ value }}</span>
          </template>
        </InlineEditableField>
        <p class="wb-hint">{{ protagonist.role || 'Protagonist' }}</p>
      </div>

      <div class="space-y-1">
        <p class="wb-label">Bio</p>
        <InlineEditableField
          :value="textOf('description')"
          type="textarea"
          :maxlength="1000"
          required
          :use-references="true"
          :reference-options="referenceOptions"
          :is-saving="isSavingText"
          edit-id="description"
          :active-edit-id="activeEditId"
          empty-text="No biography set. Click to describe your character."
          @save="emit('save-field', 'description', $event)"
          @start-edit="activeEditId = $event"
        >
          <template #default="{ value }">
            <p class="wb-body" v-html="formatObjectIds(String(value))"></p>
          </template>
        </InlineEditableField>
      </div>

      <div class="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div v-for="field in TEXT_FIELDS" :key="field.key" class="space-y-1">
          <p class="wb-label">{{ field.label }}</p>
          <InlineEditableField
            :value="textOf(field.key)"
            type="textarea"
            :maxlength="200"
            :use-references="true"
            :reference-options="referenceOptions"
            :is-saving="isSavingText"
            :edit-id="field.key"
            :active-edit-id="activeEditId"
            :empty-text="field.empty"
            @save="emit('save-field', field.key, $event)"
            @start-edit="activeEditId = $event"
          >
            <template #default="{ value }">
              <p class="wb-body" v-html="formatObjectIds(String(value))"></p>
            </template>
          </InlineEditableField>
        </div>
      </div>

      <!-- Voice of the player's own lines; saved as soon as it changes. -->
      <NpcVoicePicker
        :model-value="protagonist.voice || ''"
        :voice-list="voiceList ?? null"
        :npc-name="protagonist.name"
        :adventure-id="adventureId"
        @update:model-value="emit('save-field', 'voice', $event)"
      />

      <div class="space-y-1">
        <p class="wb-label">Appearance keywords</p>
        <InlineEditableField
          :value="protagonist.appearance ?? ''"
          type="text"
          :maxlength="100"
          placeholder="lean young woman, short red hair, leather coat, brass goggles"
          :is-saving="isSavingText"
          edit-id="appearance"
          :active-edit-id="activeEditId"
          empty-text="No appearance keywords set. Click to add visual keywords for image generation."
          @save="emit('save-field', 'appearance', $event)"
          @start-edit="activeEditId = $event"
        >
          <template #default="{ value }">
            <p class="wb-body">{{ value }}</p>
          </template>
        </InlineEditableField>
      </div>

      <div v-if="adventureId" class="border-t border-wb-line pt-6">
        <TalentsEditor
          :adventure-id="adventureId"
          :owner-name="protagonist.name ?? ''"
          :talents="protagonist.stats?.talents ?? []"
          :reference-options="referenceOptions"
          @saved="emit('talents-saved')"
        />
      </div>
    </div>
  </div>
</template>
