<script setup lang="ts">
import { computed } from 'vue'
import { BookOpen, Dices, MessageCircle } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { formFieldError } from '@/composables/editor/useEditorFormDraft'
import OverviewCover from '@/components/editor/overview/OverviewCover.vue'
import FormTextField from '@/components/editor/overview/FormTextField.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiRadioCards from '@/components/ui/UiRadioCards.vue'
import type { RadioCardOption } from '@/components/ui/UiRadioCards.vue'

/** Title, version, teaser, play style and cover of the adventure. */
const editor = useEditor()
const form = computed(() => editor.form as Record<string, unknown>)

type RuleMode = 'rpg' | 'story' | 'chat'

const MODES: RadioCardOption<RuleMode>[] = [
  { value: 'rpg', label: 'RPG', description: 'Strict mechanics: stats, dice checks and combat.', icon: Dices },
  { value: 'story', label: 'Story', description: 'Streamlined mechanics; the story leads.', icon: BookOpen },
  { value: 'chat', label: 'Chat', description: 'Pure narrative without game mechanics.', icon: MessageCircle },
]

function text(field: string): string {
  return String(form.value[field] ?? '')
}

function setText(field: string, value: string | number | null): void {
  form.value[field] = String(value ?? '')
}
</script>

<template>
  <UiCard title="Details" description="What players see in the portal and how strictly the rules are played.">
    <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_220px]">
      <div class="min-w-0 space-y-5">
        <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_160px]">
          <UiField label="Title" required :error="formFieldError(form, 'title')" :count="text('title').length" :max-length="50">
            <UiInput :model-value="text('title')" maxlength="50" @update:model-value="(v) => setText('title', v)" />
          </UiField>
          <UiField label="Version" :error="formFieldError(form, 'version')">
            <UiInput :model-value="text('version')" maxlength="15" mono placeholder="1.0.0" @update:model-value="(v) => setText('version', v)" />
          </UiField>
        </div>
        <FormTextField field="teaser" label="Teaser" hint="One or two catchy lines for the portal card." :rows="3" />
        <div class="space-y-2">
          <p class="wb-label">Play style</p>
          <UiRadioCards v-model="editor.form.rule_enforcement_mode" :options="MODES" label="Play style" :columns="3" />
        </div>
      </div>
      <OverviewCover />
    </div>
  </UiCard>
</template>
