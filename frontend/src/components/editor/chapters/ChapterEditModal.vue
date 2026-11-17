<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check } from 'lucide-vue-next'
import type { Chapter, ChapterReference, ProgressionMode } from '@/composables/editor/useChapters'
import ChapterGeneralForm from '@/components/editor/chapters/ChapterGeneralForm.vue'
import ChapterTriggersForm from '@/components/editor/chapters/ChapterTriggersForm.vue'
import SequenceScriptsEditor from '@/components/editor/SequenceScriptsEditor.vue'
import SoftRulesEditor from '@/components/editor/SoftRulesEditor.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiTabs from '@/components/ui/UiTabs.vue'

/** Edits one chapter in a dialog; "Save chapter" stores the whole chapter list. */
const open = defineModel<boolean>('open', { required: true })
const chapter = defineModel<Chapter>('chapter', { required: true })

const props = defineProps<{
  isNew: boolean
  mode: ProgressionMode
  saving: boolean
  takenIds: string[]
  references: ChapterReference[]
}>()

const emit = defineEmits<{ save: [] }>()

type Tab = 'general' | 'triggers' | 'soft_rules' | 'scripts'
const tab = ref<Tab>('general')
watch(open, (isOpen) => {
  if (isOpen) tab.value = 'general'
})

const hasTriggers = computed(() =>
  Boolean(chapter.value.on_start_sequence_script || chapter.value.on_end_sequence_script || chapter.value.helpers_script),
)
const tabs = computed(() => [
  { id: 'general' as const, label: 'General' },
  { id: 'triggers' as const, label: 'Start & end', count: hasTriggers.value ? 1 : null },
  { id: 'soft_rules' as const, label: 'Soft rules', count: chapter.value.soft_rules?.length || null },
  { id: 'scripts' as const, label: 'Scripts', count: chapter.value.scripts?.length || null },
])
const scenes = computed(() => props.references.filter((r) => r.type === 'SCENE'))
const interactTargets = computed(() => props.references.filter((r) => r.type !== 'SCENE'))
const title = computed(() => (props.isNew ? 'New chapter' : `Edit chapter: ${chapter.value.title || chapter.value.id}`))
const description = computed(() => `Goal, completion rules and scripts of this ${props.mode === 'dynamic' ? 'sequence' : 'chapter'}.`)
</script>

<template>
  <UiModal v-model:open="open" :title="title" :description="description" size="xl" :persistent="saving">
    <div class="space-y-5">
      <UiTabs v-model="tab" :tabs="tabs" label="Chapter sections" />
      <ChapterGeneralForm
        v-show="tab === 'general'"
        v-model="chapter"
        :is-new="isNew"
        :mode="mode"
        :taken-ids="takenIds"
        :references="references"
      />
      <ChapterTriggersForm v-show="tab === 'triggers'" v-model="chapter" :mode="mode" />
      <SoftRulesEditor v-show="tab === 'soft_rules'" v-model="chapter.soft_rules" />
      <SequenceScriptsEditor v-show="tab === 'scripts'" v-model="chapter.scripts" :scenes="scenes" :entities="interactTargets" />
    </div>
    <template #footer>
      <UiButton :disabled="saving" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :icon="Check" :loading="saving" :disabled="!String(chapter.title || '').trim()" @click="emit('save')">
        {{ isNew ? 'Create chapter' : 'Save chapter' }}
      </UiButton>
    </template>
  </UiModal>
</template>
