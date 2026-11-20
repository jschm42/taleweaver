<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { FileJson, Sparkles, Trash2 } from 'lucide-vue-next'
import { audioSettingsService, type AudioSettings, type AudioTestRun } from '@/services/audioSettingsService'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const POLL_MS = 2000

const PROVIDERS = [
  { value: 'lyria', label: 'Google Lyria (Gemini API key)' },
  { value: 'comfyui', label: 'ComfyUI workflow (local, experimental)' },
]

const toast = useToast()
const saved = ref<AudioSettings | null>(null)
const { draft: settings, isDirty, changedCount, isSaving, reset, commit } = useDraft(() => saved.value)
const isTesting = ref(false)
const testElapsed = ref(0)
let pollTimer: ReturnType<typeof setInterval> | undefined
const loadError = ref('')
const testPrompt = ref('slow dark ambient, low strings, distant choir, mysterious dungeon')
const testUrl = ref('')

function report(err: unknown): void {
  toast.error(err instanceof Error ? err.message : String(err))
}

onMounted(async (): Promise<void> => {
  try {
    saved.value = await audioSettingsService.load()
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err)
  }
})

async function save(): Promise<void> {
  try {
    let result: AudioSettings | null = null
    await commit(async (s) => {
      if (!s) return
      result = await audioSettingsService.save({
        enabled: s.enabled,
        comfyui_url: s.comfyui_url,
        comfyui_timeout: s.comfyui_timeout,
        comfyui_output_node_id: s.comfyui_output_node_id,
        default_duration: s.default_duration,
        max_duration: s.max_duration,
        max_generations_per_session: s.max_generations_per_session,
        provider: s.provider,
        lyria_clip_model: s.lyria_clip_model,
        lyria_full_model: s.lyria_full_model,
        lyria_timeout: s.lyria_timeout,
        lyria_wav: s.lyria_wav,
      })
    })
    if (result) saved.value = result
    toast.success('Audio settings saved.')
  } catch (err) {
    report(err)
  }
}

async function onWorkflowFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    saved.value = await audioSettingsService.uploadWorkflow(file)
    toast.success(`Workflow "${file.name}" stored.`)
  } catch (err) {
    report(err)
  }
}

async function removeWorkflow(): Promise<void> {
  try {
    saved.value = await audioSettingsService.removeWorkflow()
    toast.success('Workflow removed.')
  } catch (err) {
    report(err)
  }
}

function finishTest(run: AudioTestRun): void {
  stopPolling()
  isTesting.value = false
  if (run.status === 'failed') {
    report(new Error(`${run.error || 'Audio generation failed.'} (after ${run.elapsed} s)`))
    return
  }
  testUrl.value = run.url || ''
  toast.show(`Test clip rendered in ${run.elapsed} s (${Math.round((run.bytes || 0) / 1024)} KiB).`, { tone: 'ai' })
}

function stopPolling(): void {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = undefined
}

async function poll(id: string): Promise<void> {
  try {
    const run = await audioSettingsService.testStatus(id)
    testElapsed.value = run.elapsed
    if (run.status !== 'running') finishTest(run)
  } catch (err) {
    // One failed poll (e.g. a slow request) is not fatal; a missing run is.
    if (err instanceof Error && err.message.includes('not found')) {
      stopPolling()
      isTesting.value = false
      report(err)
    }
  }
}

async function runTest(): Promise<void> {
  isTesting.value = true
  testUrl.value = ''
  testElapsed.value = 0
  try {
    const run = await audioSettingsService.startTest(testPrompt.value, saved.value?.default_duration)
    pollTimer = setInterval(() => poll(run.id), POLL_MS)
  } catch (err) {
    isTesting.value = false
    report(err)
  }
}

onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Music & audio">
      <template #badge>
        <UiBadge tone="warn">Experimental</UiBadge>
      </template>
      <template #description>
        Generated music for the audio libraries of adventures and for scripts that compose during play with
        <code class="wb-mono">tw.audio.generate()</code>.
      </template>
    </PageHeader>

    <p v-if="loadError" class="wb-body text-wb-danger-text" role="alert">{{ loadError }}</p>
    <div v-else-if="!settings" class="flex justify-center py-10"><UiSpinner label="Loading audio settings" /></div>

    <template v-else>
      <UiCard title="Generation">
        <div class="space-y-5">
          <UiToggle
            v-model="settings.enabled"
            label="Enable audio generation"
            description="Off: nothing new is rendered, neither by scripts nor in the editor. Existing tracks still play."
          />
          <UiField label="Provider">
            <UiSelect v-model="settings.provider" :options="PROVIDERS" />
          </UiField>
          <div class="grid gap-4 sm:grid-cols-3">
            <UiField label="Default length" hint="Seconds, 5–300.">
              <UiInput v-model="settings.default_duration" type="number" min="5" max="300" />
            </UiField>
            <UiField label="Maximum length" hint="Seconds, 5–600.">
              <UiInput v-model="settings.max_duration" type="number" min="5" max="600" />
            </UiField>
            <UiField label="Tracks per play session" hint="0–500.">
              <UiInput v-model="settings.max_generations_per_session" type="number" min="0" max="500" />
            </UiField>
          </div>
        </div>
      </UiCard>

      <UiCard
        v-if="settings.provider === 'lyria'"
        title="Google Lyria"
        description="Uses the Google (Gemini) key from API keys and its key policy."
      >
        <div class="space-y-5">
          <p class="wb-body text-wb-muted">
            Requests up to 30 seconds use the clip model (fixed 30-second loops, good for scenes); longer ones use the
            full model, whose length follows the prompt. Lyria blocks artist names and lyrics, and every track carries an
            inaudible SynthID watermark.
          </p>
          <div class="grid gap-4 sm:grid-cols-3">
            <UiField label="Clip model" hint="Up to 30 seconds.">
              <UiInput v-model="settings.lyria_clip_model" class="wb-mono" />
            </UiField>
            <UiField label="Full model" hint="Longer tracks.">
              <UiInput v-model="settings.lyria_full_model" class="wb-mono" />
            </UiField>
            <UiField label="Timeout" hint="Seconds, 10–1800.">
              <UiInput v-model="settings.lyria_timeout" type="number" min="10" max="1800" />
            </UiField>
          </div>
          <UiCheckbox v-model="settings.lyria_wav" label="WAV output for the full model" description="Larger files; MP3 otherwise." />
        </div>
      </UiCard>

      <UiCard v-if="settings.provider === 'comfyui'" title="ComfyUI workflow">
        <div class="space-y-5">
          <p class="wb-body text-wb-muted">
            Build a text-to-audio workflow in ComfyUI (for example an ACE-Step template) and export it with
            <strong class="text-wb-body">Workflow › Export (API)</strong>. Before exporting, write
            <code v-pre class="wb-mono">{{prompt}}</code> into the prompt or tags field. Optional placeholders:
            <code v-pre class="wb-mono">{{negative_prompt}}</code>, <code v-pre class="wb-mono">{{seed}}</code> and
            <code v-pre class="wb-mono">{{duration}}</code> (seconds; a field holding only the placeholder becomes a number).
            The workflow must end in a SaveAudio, SaveAudioMP3 or SaveAudioOpus node.
          </p>
          <div class="flex flex-wrap items-center gap-3">
            <label class="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-wb-line-strong bg-wb-raised px-4 wb-body font-medium text-wb-strong hover:bg-wb-overlay focus-within:ring-2 focus-within:ring-wb-accent">
              <FileJson class="h-4 w-4" aria-hidden="true" />
              Upload workflow JSON
              <input type="file" accept="application/json,.json" class="sr-only" @change="onWorkflowFile" />
            </label>
            <template v-if="saved?.has_workflow">
              <span class="wb-body text-wb-body">
                {{ saved.comfyui_workflow_name || 'workflow.json' }} · {{ saved.workflow_node_count }} nodes
              </span>
              <UiButton variant="ghost" size="sm" :icon="Trash2" class="!text-wb-danger-text" @click="removeWorkflow">Remove</UiButton>
            </template>
            <span v-else class="wb-body text-wb-faint">No workflow uploaded.</span>
          </div>
          <div class="grid gap-4 sm:grid-cols-3">
            <UiField label="ComfyUI server URL" class="sm:col-span-2">
              <UiInput v-model="settings.comfyui_url" type="url" placeholder="http://127.0.0.1:8188" />
            </UiField>
            <UiField label="Timeout" hint="Seconds, 1–3600.">
              <UiInput v-model="settings.comfyui_timeout" type="number" min="1" max="3600" />
            </UiField>
            <UiField label="Output node ID" hint="Optional; default is the first node with audio.">
              <UiInput v-model="settings.comfyui_output_node_id" />
            </UiField>
          </div>
          <p class="wb-hint">
            The backend connects to this URL. Private or LAN addresses need ALLOW_PRIVATE_NETWORK_MODELS=true. One track
            renders at a time.
          </p>
        </div>
      </UiCard>

      <UiCard title="Test run" description="Renders one clip with the saved settings.">
        <div class="space-y-4">
          <p v-if="isDirty" class="wb-hint !text-wb-warn-text">Save your changes first; the test uses the saved settings.</p>
          <p class="wb-hint">The first run can take minutes while the model loads; the timeout above limits it.</p>
          <UiField label="Prompt">
            <UiTextarea v-model="testPrompt" :rows="2" maxlength="1000" />
          </UiField>
          <div class="flex flex-wrap items-center gap-4">
            <UiButton
              variant="ai"
              :icon="Sparkles"
              :loading="isTesting"
              :disabled="(saved?.provider === 'comfyui' && !saved?.has_workflow) || !testPrompt.trim()"
              @click="runTest"
            >
              {{ isTesting ? `Composing… ${testElapsed} s` : 'Generate test clip' }}
            </UiButton>
            <audio v-if="testUrl" :src="testUrl" controls class="h-9"></audio>
          </div>
        </div>
      </UiCard>
    </template>

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
