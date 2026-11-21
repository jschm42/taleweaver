<script setup lang="ts">
/**
 * Narrator personas: tile overview like the style and tone catalogs. Edits, restore and
 * import change the local draft; the save bar stores the catalog.
 */
import { computed, onMounted, ref } from 'vue'
import { Download, FileUp, Pencil, Plus, RotateCcw, ScrollText, Trash2 } from 'lucide-vue-next'
import { narratorVoiceService, type NarratorVoice } from '@/services/narratorVoiceService'
import { confirmDialog } from '@/composables/useDialogs'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import {
  buildCatalogFile,
  catalogFileName,
  downloadJson,
  mergeCatalog,
  parseCatalogFile,
} from '@/components/admin/catalogTransfer'
import PersonaEditModal from '@/components/admin/PersonaEditModal.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiMenu, { type MenuItem } from '@/components/ui/UiMenu.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

const toast = useToast()
const saved = ref<NarratorVoice[]>([])
const defaults = ref<NarratorVoice[]>([])
const isLoading = ref(true)
const loadError = ref('')
const importInput = ref<HTMLInputElement | null>(null)
const editIndex = ref<number | null>(null)
const isEditorOpen = ref(false)

const { draft: voices, isDirty, changedCount, isSaving, reset, commit } = useDraft(() => saved.value)

const copy = (list: NarratorVoice[]): NarratorVoice[] => list.map((voice) => ({ ...voice }))

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

const editingVoice = computed(() => (editIndex.value === null ? null : voices.value[editIndex.value]))

function openEditor(index: number | null): void {
  editIndex.value = index
  isEditorOpen.value = true
}

function applyVoice(voice: NarratorVoice): void {
  if (editIndex.value === null) {
    voices.value.push(voice)
    return
  }
  voices.value[editIndex.value] = voice
}

async function removeVoice(index: number): Promise<void> {
  const name = voices.value[index]?.name || 'this persona'
  const confirmed = await confirmDialog({
    title: `Remove "${name}"?`,
    message: 'The persona is removed when you save. Adventures keep their own copy.',
    confirmLabel: 'Remove',
    danger: true,
  })
  if (confirmed) voices.value.splice(index, 1)
}

function mergeIntoDraft(incoming: NarratorVoice[], done: string): void {
  const result = mergeCatalog(voices.value, incoming)
  voices.value = result.items
  toast.success(`${done}: ${result.replaced} updated, ${result.added} added. Review and save.`)
}

async function restoreDefaults(): Promise<void> {
  const confirmed = await confirmDialog({
    title: 'Restore the default personas?',
    message: 'Built-in personas get their original text back; missing ones are added. Your own personas stay. Nothing is stored until you save.',
    confirmLabel: 'Restore defaults',
  })
  if (confirmed) mergeIntoDraft(copy(defaults.value), 'Defaults restored')
}

async function onImportFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    mergeIntoDraft(parseCatalogFile(await file.text(), 'personas') as NarratorVoice[], 'Imported')
  } catch (err) {
    toast.error(`Import failed: ${(err as Error).message}`)
  }
}

function exportPersonas(): void {
  downloadJson(catalogFileName('personas'), buildCatalogFile('personas', saved.value))
  toast.success(isDirty.value ? 'Exported the saved personas (unsaved changes are not included).' : 'Personas exported.')
}

const pageMenu = computed<MenuItem[]>(() => [
  { label: 'Import from file…', icon: FileUp, onSelect: () => importInput.value?.click() },
  { label: 'Export to file', icon: Download, disabled: !saved.value.length, onSelect: exportPersonas },
  { label: 'Restore defaults…', icon: RotateCcw, separated: true, onSelect: () => void restoreDefaults() },
])

function tileMenu(index: number): MenuItem[] {
  return [
    { label: 'Edit', icon: Pencil, onSelect: () => openEditor(index) },
    { label: 'Remove', icon: Trash2, tone: 'danger', separated: true, onSelect: () => void removeVoice(index) },
  ]
}

const save = async (): Promise<void> => {
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
        <UiMenu :items="pageMenu" label="Import, export and restore personas" />
        <input ref="importInput" type="file" accept=".json,application/json" class="hidden" @change="onImportFile" />
        <UiButton variant="primary" :icon="Plus" @click="openEditor(null)">Add persona</UiButton>
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
          <UiButton variant="primary" :icon="Plus" @click="openEditor(null)">Add persona</UiButton>
        </template>
      </UiEmptyState>

      <ul v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <li
          v-for="(voice, index) in voices"
          :key="(voice.id || 'new') + '-' + index"
          class="relative flex flex-col rounded-xl border border-wb-line bg-wb-surface transition-colors hover:border-wb-line-strong"
        >
          <div class="absolute right-2 top-2">
            <UiMenu :items="tileMenu(index)" :label="`Actions for ${voice.name || 'this persona'}`" />
          </div>
          <button
            type="button"
            class="flex flex-1 flex-col gap-2 rounded-xl p-4 pr-12 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
            @click="openEditor(index)"
          >
            <span class="flex items-center gap-2">
              <ScrollText class="h-4 w-4 shrink-0 text-wb-faint" aria-hidden="true" />
              <span class="wb-label truncate !text-wb-strong">{{ voice.name || 'New persona' }}</span>
            </span>
            <span v-if="voice.id" class="wb-mono truncate text-wb-faint">{{ voice.id }}</span>
            <span class="wb-hint line-clamp-2">{{ voice.description || 'No description.' }}</span>
            <span v-if="voice.sample" class="wb-body line-clamp-3 border-l-2 border-wb-line-strong pl-3 italic text-wb-muted">
              {{ voice.sample }}
            </span>
          </button>
        </li>
      </ul>
    </template>

    <PersonaEditModal v-model:open="isEditorOpen" :voice="editingVoice" :is-new="editIndex === null" @apply="applyVoice" />

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
