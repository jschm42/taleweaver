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
import { api } from '@/composables/useApi'
import type { VoiceMapFileFormat, VoiceMapRow, VoiceMapTable } from '@/types'


const rows = ref<VoiceMapRow[]>([])
const googleVoices = ref<VoiceMapTable['google_voices']>([])
const compatibleVoices = ref<string[]>([])
const filter = ref('')
const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const notice = ref('')
const importInput = ref<HTMLInputElement | null>(null)

const filteredRows = computed((): VoiceMapRow[] => {
  const needle = filter.value.trim().toLowerCase()
  if (!needle) return rows.value
  return rows.value.filter((row) =>
    [row.name, row.description, row.elevenlabs, row.google, row.custom_openai].some((text) => text?.toLowerCase().includes(needle)),
  )
})
const googleCount = computed((): number => rows.value.filter((row) => row.google).length)
const compatibleCount = computed((): number => rows.value.filter((row) => row.custom_openai).length)

const suggestionCount = computed((): number =>
  rows.value.filter((row) => (!row.google && row.suggested_google) || (!row.custom_openai && row.suggested_custom_openai)).length,
)

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
  error.value = ''
  notice.value = ''
  try {
    const table = await api.getVoiceMap()
    rows.value = table.items
    googleVoices.value = table.google_voices
  } catch (err) {
    error.value = `Could not load the voice mapping: ${errorText(err)}`
  } finally {
    isLoading.value = false
  }
  void loadCompatibleVoices()
}

onMounted(load)

async function save(): Promise<void> {
  isSaving.value = true
  error.value = ''
  notice.value = ''
  try {
    rows.value = (await api.saveVoiceMap(rows.value)).items
    notice.value = 'Voice mapping saved.'
  } catch (err) {
    error.value = errorText(err)
  } finally {
    isSaving.value = false
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
  error.value = ''
  try {
    const { filename, content } = await api.exportVoiceMap(format, rows.value)
    downloadFile(filename, content, format)
  } catch (err) {
    error.value = `Export failed: ${errorText(err)}`
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
  error.value = ''
  notice.value = ''
  const format: VoiceMapFileFormat = file.name.toLowerCase().endsWith('.json') ? 'json' : 'csv'
  try {
    const result = await api.importVoiceMap(await file.text(), format, rows.value)
    rows.value = result.items
    notice.value = importSummary(result.matched, result.unknown, result.errors)
  } catch (err) {
    error.value = `Import failed: ${errorText(err)}`
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-6xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight">Character Voices</h1>
        <p class="text-slate-400 text-sm mt-1 max-w-3xl">
          Characters pick their voice from the voice list. ElevenLabs speaks the listed ids; for Google TTS and the
          OpenAI-compatible server, enter the voice that should speak each one. An empty cell uses the narrator (GM) voice.
        </p>
      </div>
      <button
        type="button"
        :disabled="isSaving || isLoading"
        class="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-blue-900/30 disabled:opacity-50 flex items-center gap-2 self-start sm:self-auto cursor-pointer shrink-0"
        @click="save"
      >
        <i v-if="isSaving" class="ra ra-recycle animate-spin"></i>
        <i v-else class="ra ra-save"></i>
        <span>{{ isSaving ? 'Saving...' : 'Save Mapping' }}</span>
      </button>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-4">
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="filter"
          type="search"
          placeholder="Filter voices…"
          aria-label="Filter voices"
          class="flex-1 min-w-[12rem] bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-blue-500/50"
        />
        <span class="text-[11px] text-slate-500">Google {{ googleCount }}/{{ rows.length }} · OpenAI-compatible {{ compatibleCount }}/{{ rows.length }}</span>
        <button
          type="button"
          class="vm-btn"
          :disabled="!suggestionCount"
          title="Fill empty cells with the voices suggested in the voice list"
          @click="applySuggestions"
        >
          Use Suggestions
        </button>
        <button type="button" class="vm-btn" @click="importInput?.click()">Import…</button>
        <button type="button" class="vm-btn" @click="exportTable('csv')">Export CSV</button>
        <button type="button" class="vm-btn" @click="exportTable('json')">Export JSON</button>
        <input ref="importInput" type="file" accept=".csv,.json,text/csv,application/json" class="hidden" @change="onImportFile" />
      </div>

      <p v-if="error" class="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3 py-2" role="alert">{{ error }}</p>
      <p v-if="notice" class="text-xs text-emerald-200 bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-3 py-2" role="status">{{ notice }}</p>

      <div class="max-h-[65vh] overflow-auto rounded-2xl border border-slate-800">
        <p v-if="isLoading" class="p-6 text-sm text-slate-400">Loading voices…</p>
        <table v-else class="w-full text-sm">
          <thead class="sticky top-0 bg-slate-950 text-[10px] uppercase tracking-wider text-slate-500">
            <tr>
              <th class="text-left px-3 py-2 font-bold">Voice</th>
              <th class="text-left px-3 py-2 font-bold">ElevenLabs ID</th>
              <th class="text-left px-3 py-2 font-bold">Google TTS</th>
              <th class="text-left px-3 py-2 font-bold">OpenAI-compatible</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="row.id" class="border-t border-slate-800/70 align-top">
              <td class="px-3 py-2">
                <div class="font-bold text-white">{{ row.name }}</div>
                <div class="text-[11px] text-slate-500">{{ traits(row) }}</div>
              </td>
              <td class="px-3 py-2 font-mono text-[11px] text-slate-400 whitespace-nowrap">{{ row.elevenlabs }}</td>
              <td class="px-3 py-2">
                <select v-model="row.google" :aria-label="`Google voice for ${row.name}`" class="vm-input" style="color-scheme: dark">
                  <option value="">Narrator voice</option>
                  <option v-for="voice in googleVoices" :key="voice.name" :value="voice.name">{{ googleLabel(voice) }}</option>
                </select>
              </td>
              <td class="px-3 py-2">
                <input
                  v-model.trim="row.custom_openai"
                  list="vm-compatible-voices"
                  maxlength="200"
                  placeholder="Narrator voice"
                  :aria-label="`OpenAI-compatible voice for ${row.name}`"
                  class="vm-input"
                />
              </td>
            </tr>
            <tr v-if="!filteredRows.length">
              <td colspan="4" class="px-3 py-6 text-center text-slate-500">No voices match.</td>
            </tr>
          </tbody>
        </table>
        <datalist id="vm-compatible-voices">
          <option v-for="voice in compatibleVoices" :key="voice" :value="voice" />
        </datalist>
      </div>

    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.vm-btn {
  padding: 0.5rem 0.9rem;
  border-radius: 0.75rem;
  border: 1px solid rgb(51 65 85 / 0.8);
  background: rgb(15 23 42 / 0.8);
  color: rgb(203 213 225);
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.vm-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.vm-btn:hover:not(:disabled) {
  color: white;
  border-color: rgb(59 130 246 / 0.6);
}
.vm-input {
  width: 100%;
  min-width: 10rem;
  background: rgb(2 6 23);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.6rem;
  padding: 0.4rem 0.6rem;
  color: white;
  font-size: 0.8rem;
  outline: none;
}
.vm-input:focus {
  box-shadow: 0 0 0 2px rgb(59 130 246 / 0.5);
}
.vm-input option {
  background: rgb(15 23 42);
  color: white;
}
</style>
