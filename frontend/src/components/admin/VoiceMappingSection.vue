<script setup lang="ts">
/**
 * VoiceMappingSection — Admin page: which Google TTS / OpenAI-compatible voice speaks each voice of the voice list.
 *
 * Characters store a voice from the voice list (ElevenLabs ids). Google and OpenAI-compatible
 * servers speak the voice entered here; an empty cell means the narrator (GM) voice. The table can
 * be exported as CSV / JSON, edited in a spreadsheet and imported again (import only fills the
 * table; Save stores it). Until a mapping is saved, the voice list's suggestions are shown.
 */
import { computed, onMounted, ref } from 'vue'
import { Download, FileUp, RotateCcw, Search, Wand2 } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { confirmDialog } from '@/composables/useDialogs'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import type { VoiceMapFileFormat, VoiceMapRow, VoiceMapTable } from '@/types'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiMenu, { type MenuItem } from '@/components/ui/UiMenu.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

const toast = useToast()
const saved = ref<VoiceMapRow[]>([])
const { draft: rows, isDirty, changedCount, isSaving, reset, adopt, commit } = useDraft(() => saved.value)
const googleVoices = ref<VoiceMapTable['google_voices']>([])
const compatibleVoices = ref<string[]>([])
const filter = ref('')
const isLoading = ref(false)
const loadError = ref('')
const notice = ref('')
const importInput = ref<HTMLInputElement | null>(null)

function bestForTags(row: VoiceMapRow): string[] {
  const list = row.best_for ?? row.good_for
  return Array.isArray(list) ? list : []
}

const filteredRows = computed((): VoiceMapRow[] => {
  const needle = filter.value.trim().toLowerCase()
  if (!needle) return rows.value
  return rows.value.filter((row) =>
    [
      row.name,
      row.description,
      row.elevenlabs,
      row.google,
      row.custom_openai,
      ...bestForTags(row),
    ].some((text) => text?.toLowerCase().includes(needle)),
  )
})
const googleCount = computed((): number => rows.value.filter((row) => row.google).length)
const compatibleCount = computed((): number => rows.value.filter((row) => row.custom_openai).length)

const suggestionCount = computed((): number =>
  rows.value.filter((row) => (!row.google && row.suggested_google) || (!row.custom_openai && row.suggested_custom_openai)).length,
)

const googleOptions = computed(() => [
  { value: '', label: 'Narrator voice' },
  ...googleVoices.value.map((voice) => ({ value: voice.name, label: googleLabel(voice) })),
])

/** Fills empty cells with the voice list's suggestions; filled cells are kept. */
function applySuggestions(): void {
  for (const row of rows.value) {
    row.google = row.google || row.suggested_google
    row.custom_openai = row.custom_openai || row.suggested_custom_openai
  }
  notice.value = 'Empty cells were filled with the suggested voices. Review and save.'
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function traits(row: VoiceMapRow): string {
  return [row.gender, row.age, row.accent, row.description].filter(Boolean).join(' · ')
}

function googleLabel(voice: VoiceMapTable['google_voices'][number]): string {
  const details = [voice.gender, voice.description].filter(Boolean).join(', ')
  return details ? `${voice.name} (${details})` : voice.name
}

async function loadCompatibleVoices(): Promise<void> {
  try {
    compatibleVoices.value = (await api.getSpeechVoices()).voices
  } catch {
    // No OpenAI-compatible server configured or reachable: voices are typed in by hand.
    compatibleVoices.value = []
  }
}

async function load(): Promise<void> {
  isLoading.value = true
  loadError.value = ''
  notice.value = ''
  try {
    const table = await api.getVoiceMap()
    saved.value = table.items
    googleVoices.value = table.google_voices
  } catch (err) {
    loadError.value = `Could not load the voice mapping: ${errorText(err)}`
  } finally {
    isLoading.value = false
  }
  void loadCompatibleVoices()
}

onMounted(load)

async function save(): Promise<void> {
  notice.value = ''
  try {
    let result: VoiceMapRow[] = []
    await commit(async (list) => {
      result = (await api.saveVoiceMap(list)).items
    })
    saved.value = result
    toast.success('Voice mapping saved.')
  } catch (err) {
    toast.error(errorText(err))
  }
}

async function resetToDefaults(): Promise<void> {
  const confirmed = await confirmDialog({
    title: 'Reset the voice mapping?',
    message:
      'This clears all saved Google TTS and OpenAI-compatible voices and restores the suggestions from the voice list.',
    confirmLabel: 'Reset mapping',
    danger: true,
  })
  if (!confirmed) return
  notice.value = ''
  try {
    const items = (await api.resetVoiceMap()).items
    saved.value = items
    adopt(items)
    toast.success('Voice mapping reset to defaults.')
  } catch (err) {
    toast.error(errorText(err))
  }
}

function downloadFile(filename: string, content: string, format: VoiceMapFileFormat): void {
  const type = format === 'json' ? 'application/json' : 'text/csv'
  const url = URL.createObjectURL(new Blob([content], { type: `${type};charset=utf-8` }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

async function exportTable(format: VoiceMapFileFormat): Promise<void> {
  try {
    const { filename, content } = await api.exportVoiceMap(format, rows.value)
    downloadFile(filename, content, format)
  } catch (err) {
    toast.error(`Export failed: ${errorText(err)}`)
  }
}

function importSummary(matched: number, unknown: string[], errors: string[]): string {
  const parts = [`${matched} voice${matched === 1 ? '' : 's'} updated from the file. Review and save.`]
  if (unknown.length) parts.push(`Not in the voice list (skipped): ${unknown.join(', ')}.`)
  if (errors.length) parts.push(`Invalid cells (skipped): ${errors.join('; ')}.`)
  return parts.join(' ')
}

async function onImportFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  notice.value = ''
  const format: VoiceMapFileFormat = file.name.toLowerCase().endsWith('.json') ? 'json' : 'csv'
  try {
    const result = await api.importVoiceMap(await file.text(), format, rows.value)
    rows.value = result.items
    notice.value = importSummary(result.matched, result.unknown, result.errors)
  } catch (err) {
    toast.error(`Import failed: ${errorText(err)}`)
  }
}

const menuItems = computed<MenuItem[]>(() => [
  { label: 'Import CSV or JSON…', icon: FileUp, onSelect: () => importInput.value?.click() },
  { label: 'Export CSV', icon: Download, onSelect: () => void exportTable('csv') },
  { label: 'Export JSON', icon: Download, onSelect: () => void exportTable('json') },
  {
    label: 'Reset to defaults',
    icon: RotateCcw,
    tone: 'danger',
    separated: true,
    disabled: isLoading.value || isSaving.value,
    onSelect: () => void resetToDefaults(),
  },
])
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      title="Character voices"
      description="Characters pick a voice from the voice list. ElevenLabs speaks the listed ids; for Google TTS and the OpenAI-compatible server, choose the voice that speaks each one. Empty cells use the narrator voice."
    />

    <p v-if="loadError" class="wb-body text-wb-danger-text" role="alert">{{ loadError }}</p>
    <UiNotice v-if="notice" tone="info">{{ notice }}</UiNotice>

    <UiCard :padded="false">
      <div class="flex flex-wrap items-center gap-2 border-b border-wb-line p-3">
        <div class="relative min-w-[12rem] flex-1">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-wb-faint" aria-hidden="true" />
          <UiInput v-model="filter" type="search" placeholder="Filter voices…" aria-label="Filter voices" class="pl-9" />
        </div>
        <UiBadge>Google {{ googleCount }}/{{ rows.length }}</UiBadge>
        <UiBadge>OpenAI-compatible {{ compatibleCount }}/{{ rows.length }}</UiBadge>
        <UiButton
          size="sm"
          :icon="Wand2"
          :disabled="!suggestionCount"
          title="Fill empty cells with the voices suggested in the voice list"
          @click="applySuggestions"
        >
          Use suggestions
        </UiButton>
        <UiMenu :items="menuItems" label="Import, export and reset" />
        <input ref="importInput" type="file" accept=".csv,.json,text/csv,application/json" class="hidden" @change="onImportFile" />
      </div>

      <div class="max-h-[65vh] overflow-auto">
        <div v-if="isLoading" class="flex justify-center p-8"><UiSpinner label="Loading voices" /></div>
        <table v-else class="w-full">
          <thead class="sticky top-0 z-10 bg-wb-surface">
            <tr class="border-b border-wb-line">
              <th scope="col" class="wb-label px-3 py-2 text-left !text-wb-muted">Voice</th>
              <th scope="col" class="wb-label px-3 py-2 text-left !text-wb-muted">Best for</th>
              <th scope="col" class="wb-label px-3 py-2 text-left !text-wb-muted">ElevenLabs ID</th>
              <th scope="col" class="wb-label px-3 py-2 text-left !text-wb-muted">Google TTS</th>
              <th scope="col" class="wb-label px-3 py-2 text-left !text-wb-muted">OpenAI-compatible</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-wb-line">
            <tr v-for="row in filteredRows" :key="row.id" class="align-top">
              <td class="px-3 py-2">
                <div class="wb-body font-medium text-wb-strong">{{ row.name }}</div>
                <div class="wb-hint">{{ traits(row) }}</div>
              </td>
              <td class="px-3 py-2">
                <div v-if="bestForTags(row).length" class="flex max-w-xs flex-wrap gap-1">
                  <UiBadge v-for="tag in bestForTags(row)" :key="tag">{{ tag }}</UiBadge>
                </div>
                <span v-else class="wb-hint">–</span>
              </td>
              <td class="whitespace-nowrap px-3 py-2 wb-mono text-wb-muted">{{ row.elevenlabs }}</td>
              <td class="min-w-[11rem] px-3 py-2">
                <UiSelect v-model="row.google" :options="googleOptions" size="sm" :aria-label="`Google voice for ${row.name}`" />
              </td>
              <td class="min-w-[11rem] px-3 py-2">
                <UiInput
                  v-model="row.custom_openai"
                  size="sm"
                  list="vm-compatible-voices"
                  maxlength="200"
                  placeholder="Narrator voice"
                  :aria-label="`OpenAI-compatible voice for ${row.name}`"
                />
              </td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td colspan="5" class="px-3 py-6 text-center wb-body text-wb-muted">No voices match.</td>
            </tr>
          </tbody>
        </table>
        <datalist id="vm-compatible-voices">
          <option v-for="voice in compatibleVoices" :key="voice" :value="voice" />
        </datalist>
      </div>
    </UiCard>

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
