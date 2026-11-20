<script setup lang="ts">
import { computed, ref } from 'vue'
import { Inbox, Plus, Sparkles, Trash2 } from 'lucide-vue-next'
import { useConfirm, usePrompt } from '@/composables/useDialogs'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiCombobox from '@/components/ui/UiCombobox.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiRange from '@/components/ui/UiRange.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

/** Dev-only page (/dev/ui) that shows every Workbench component in its states. */
const confirm = useConfirm()
const prompt = usePrompt()
const toast = useToast()

const saved = ref({ title: 'The Drowned Bell', tone: 'dark', clock: true, notes: '', autosave: false })
const { draft, isDirty, changedCount, isSaving, reset, commit } = useDraft(() => saved.value)

const titleError = computed(() => (draft.value.title.trim() ? null : 'A title is required.'))
const toneOptions = [
  { value: 'dark', label: 'Dark fantasy' },
  { value: 'cozy', label: 'Cozy' },
  { value: 'noir', label: 'Noir' },
]

const tabs = [
  { id: 'general', label: 'General' },
  { id: 'combat', label: 'Combat' },
  { id: 'triggers', label: 'Triggers', count: 3 },
]
const activeTab = ref('general')
const chance = ref(40)
const diceExample = ref('1d8+1')
const voiceExample = ref('my_custom_voice')
const voiceOptions = ['af_heart', 'af_bella', 'am_adam', 'bf_emma', 'bm_george']

const modalOpen = ref(false)
const drawerOpen = ref(false)

async function save(): Promise<void> {
  await commit(async (value) => {
    await new Promise((resolve) => setTimeout(resolve, 600))
    saved.value = value
  })
  toast.success('Adventure settings saved.')
}

async function askDelete(): Promise<void> {
  const yes = await confirm({
    title: 'Delete "Harbor Square"?',
    message: 'The scene and its exits are removed.',
    confirmLabel: 'Delete scene',
    danger: true,
  })
  toast.show(yes ? 'Deleted (demo).' : 'Kept.', { tone: yes ? 'error' : 'info' })
}

async function askName(): Promise<void> {
  const name = await prompt({
    title: 'Rename track',
    label: 'Track name',
    initial: 'Crypt theme',
    validate: (value) => (value.trim().length < 3 ? 'At least 3 characters.' : null),
  })
  if (name !== null) {
    toast.success(`Renamed to "${name}".`)
  }
}
</script>

<template>
  <div class="wb-root h-full overflow-y-auto bg-wb-canvas">
    <div class="mx-auto max-w-5xl space-y-6 p-6 xl:p-8">
      <header>
        <h1 class="wb-title">Workbench components</h1>
        <p class="wb-hint mt-1">Dev-only showcase of src/components/ui. See docs/specs/workbench_ui.md.</p>
      </header>

      <UiCard title="Buttons" description="One primary action per area; violet only for AI.">
        <div class="flex flex-wrap items-center gap-2">
          <UiButton variant="primary" :icon="Plus">Add scene</UiButton>
          <UiButton>Secondary</UiButton>
          <UiButton variant="ghost">Ghost</UiButton>
          <UiButton variant="danger" :icon="Trash2">Delete</UiButton>
          <UiButton variant="ai" :icon="Sparkles">Generate</UiButton>
          <UiButton variant="primary" loading>Saving</UiButton>
          <UiButton size="sm">Small</UiButton>
          <UiIconButton :icon="Trash2" label="Delete scene" variant="danger" />
        </div>
      </UiCard>

      <UiCard title="Form" description="Edit freely; the save bar appears once something changed.">
        <div class="space-y-4">
          <UiField label="Title" :error="titleError" :count="draft.title.length" :max-length="50" required>
            <UiInput v-model="draft.title" />
          </UiField>
          <UiField label="Tone" hint="Sets the narrator's mood." info="Tones come from the admin catalog.">
            <UiSelect v-model="draft.tone" :options="toneOptions" />
          </UiField>
          <UiField label="Author notes">
            <UiTextarea v-model="draft.notes" placeholder="Only visible in the editor." />
          </UiField>
          <UiField label="Damage (dice)" hint="`mono` for IDs, dice and codes.">
            <UiInput v-model="diceExample" mono />
          </UiField>
          <UiField label="Voice" hint="Free text with suggestions; the chevron always lists every option.">
            <UiCombobox v-model="voiceExample" :options="voiceOptions" mono />
          </UiField>
          <UiField label="Special attack chance">
            <UiRange v-model="chance" :step="5" unit="%" />
          </UiField>
          <UiToggle v-model="draft.clock" label="In-game clock" description="Advance time with every message." />
          <UiSection title="Advanced" description="2 options" collapsible>
            <UiCheckbox v-model="draft.autosave" label="Save before each chapter" />
          </UiSection>
        </div>
      </UiCard>

      <UiCard title="Tabs" description="Arrow keys move between tabs; the caller renders the panels.">
        <UiTabs v-model="activeTab" :tabs="tabs" label="Demo tabs" />
        <p class="wb-body mt-4 text-wb-muted">Panel: {{ activeTab }}</p>
      </UiCard>

      <UiCard title="Dialogs and feedback">
        <div class="flex flex-wrap gap-2">
          <UiButton @click="askDelete">useConfirm()</UiButton>
          <UiButton @click="askName">usePrompt()</UiButton>
          <UiButton @click="modalOpen = true">UiModal</UiButton>
          <UiButton @click="drawerOpen = true">UiDrawer</UiButton>
          <UiButton @click="toast.info('Validation finished: 2 warnings.')">Toast</UiButton>
          <UiButton @click="toast.error('Could not reach the image provider.')">Error toast</UiButton>
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <UiBadge>12</UiBadge>
          <UiBadge tone="accent">Active</UiBadge>
          <UiBadge tone="ai">Generating</UiBadge>
          <UiBadge tone="info">Hint</UiBadge>
          <UiBadge tone="warn">2 warnings</UiBadge>
          <UiBadge tone="danger">1 error</UiBadge>
          <UiSpinner />
        </div>
      </UiCard>

      <UiEmptyState :icon="Inbox" title="No side quests yet" description="Side quests reward exploration off the main path.">
        <template #action>
          <UiButton variant="primary" :icon="Plus">Add side quest</UiButton>
        </template>
      </UiEmptyState>

      <UiSaveBar
        :dirty="isDirty"
        :count="changedCount"
        :saving="isSaving"
        :error-count="titleError ? 1 : 0"
        @save="save"
        @discard="reset"
      />
    </div>

    <UiModal v-model:open="modalOpen" title="Move item to scene" description="Pick the scene that should hold the item.">
      <UiField label="Scene">
        <UiSelect :options="[{ value: 'HARBOR', label: 'Harbor Square' }]" placeholder="Choose a scene" />
      </UiField>
      <template #footer>
        <UiButton @click="modalOpen = false">Cancel</UiButton>
        <UiButton variant="primary" @click="modalOpen = false">Move</UiButton>
      </template>
    </UiModal>

    <UiDrawer v-model:open="drawerOpen" title="World-Builder" description="Describe a change; you review it before it is applied.">
      <UiField label="Instruction">
        <UiTextarea placeholder="Add a smugglers' cave below the harbor." :rows="5" />
      </UiField>
      <template #footer>
        <UiButton variant="ai" :icon="Sparkles">Propose changes</UiButton>
      </template>
    </UiDrawer>
  </div>
</template>
