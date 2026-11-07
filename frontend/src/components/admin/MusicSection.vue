<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { musicSettingsService, type MusicSettings } from '@/services/musicSettingsService'

const settings = ref<MusicSettings | null>(null)
const isSaving = ref(false)
const isTesting = ref(false)
const message = ref('')
const error = ref('')
const testPrompt = ref('slow dark ambient, low strings, distant choir, mysterious dungeon')
const testUrl = ref('')

function report(err: unknown): void {
  error.value = err instanceof Error ? err.message : String(err)
  message.value = ''
}

function done(text: string): void {
  message.value = text
  error.value = ''
}

onMounted(async (): Promise<void> => {
  try {
    settings.value = await musicSettingsService.load()
  } catch (err) {
    report(err)
  }
})

async function save(): Promise<void> {
  if (!settings.value) return
  isSaving.value = true
  try {
    const s = settings.value
    settings.value = await musicSettingsService.save({
      enabled: s.enabled,
      comfyui_url: s.comfyui_url,
      comfyui_timeout: s.comfyui_timeout,
      comfyui_output_node_id: s.comfyui_output_node_id,
      default_duration: s.default_duration,
      max_duration: s.max_duration,
      max_generations_per_session: s.max_generations_per_session,
    })
    done('Music settings saved.')
  } catch (err) {
    report(err)
  } finally {
    isSaving.value = false
  }
}

async function onWorkflowFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    settings.value = await musicSettingsService.uploadWorkflow(file)
    done(`Workflow "${file.name}" stored.`)
  } catch (err) {
    report(err)
  }
}

async function removeWorkflow(): Promise<void> {
  try {
    settings.value = await musicSettingsService.removeWorkflow()
    done('Workflow removed.')
  } catch (err) {
    report(err)
  }
}

async function runTest(): Promise<void> {
  isTesting.value = true
  testUrl.value = ''
  try {
    const result = await musicSettingsService.test(testPrompt.value, settings.value?.default_duration)
    testUrl.value = result.url
    done(`Test clip rendered (${Math.round(result.bytes / 1024)} KiB).`)
  } catch (err) {
    report(err)
  } finally {
    isTesting.value = false
  }
}
</script>

<template>
  <div class="space-y-6 animate-fade-in max-w-5xl">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-extrabold text-white tracking-tight">
          Music <span class="ml-2 align-middle text-xs font-bold text-amber-400">Experimental</span>
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Background music that adventure scripts compose during play with <code>tw.music.generate()</code>.
        </p>
      </div>
      <button
        type="button"
        :disabled="isSaving || !settings"
        class="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all disabled:opacity-50 self-start sm:self-auto cursor-pointer"
        @click="save"
      >
        {{ isSaving ? 'Saving...' : 'Save Music Settings' }}
      </button>
    </div>

    <p v-if="message" class="text-xs text-emerald-400">{{ message }}</p>
    <p v-if="error" class="text-xs text-rose-400">{{ error }}</p>

    <div v-if="settings" class="space-y-6">
      <section class="space-y-4 rounded-3xl border border-slate-800 bg-slate-900 p-6">
        <label class="flex items-center justify-between gap-4">
          <span>
            <span class="block text-sm font-bold text-white">Enable music generation</span>
            <span class="block text-xs text-slate-500">Off: scripts may still call tw.music, but nothing is rendered or played.</span>
          </span>
          <input v-model="settings.enabled" type="checkbox" class="h-5 w-5 accent-emerald-500" />
        </label>
        <div class="grid gap-4 sm:grid-cols-3">
          <label class="text-xs text-slate-300">Default length (seconds)
            <input v-model.number="settings.default_duration" type="number" min="5" max="300"
              class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
          </label>
          <label class="text-xs text-slate-300">Maximum length (seconds)
            <input v-model.number="settings.max_duration" type="number" min="5" max="600"
              class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
          </label>
          <label class="text-xs text-slate-300">Tracks per play session
            <input v-model.number="settings.max_generations_per_session" type="number" min="0" max="500"
              class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
          </label>
        </div>
      </section>

      <section class="space-y-4 rounded-3xl border border-amber-500/30 bg-slate-900 p-6">
        <h3 class="font-bold text-white">ComfyUI workflow</h3>
        <p class="text-xs leading-relaxed text-slate-400">
          Build a text-to-music workflow in ComfyUI (for example an ACE-Step template) and export it with
          <strong>Workflow &gt; Export (API)</strong>. Before exporting, write <code v-pre>{{prompt}}</code> into the
          prompt/tags text field. Optional placeholders: <code v-pre>{{negative_prompt}}</code>,
          <code v-pre>{{seed}}</code> and <code v-pre>{{duration}}</code> (seconds; a field holding only the
          placeholder becomes a number). The workflow must end in a SaveAudio, SaveAudioMP3 or SaveAudioOpus node.
        </p>
        <div class="flex flex-wrap items-center gap-3">
          <label class="cursor-pointer rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-xs font-bold text-white hover:border-amber-500/50">
            Upload workflow JSON
            <input type="file" accept="application/json,.json" class="hidden" @change="onWorkflowFile" />
          </label>
          <span v-if="settings.has_workflow" class="text-xs text-slate-300">
            {{ settings.comfyui_workflow_name || 'workflow.json' }} · {{ settings.workflow_node_count }} nodes
          </span>
          <span v-else class="text-xs text-slate-500">No workflow uploaded.</span>
          <button v-if="settings.has_workflow" type="button" class="text-xs text-rose-400 hover:text-rose-300" @click="removeWorkflow">
            Remove
          </button>
        </div>
        <div class="grid gap-4 sm:grid-cols-3">
          <label class="text-xs text-slate-300 sm:col-span-2">ComfyUI server URL
            <input v-model="settings.comfyui_url" type="url" placeholder="http://127.0.0.1:8188"
              class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
          </label>
          <label class="text-xs text-slate-300">Timeout (seconds)
            <input v-model.number="settings.comfyui_timeout" type="number" min="1" max="3600"
              class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
          </label>
          <label class="text-xs text-slate-300">Output node ID (optional)
            <input v-model="settings.comfyui_output_node_id" type="text" placeholder="first node with audio"
              class="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-white" />
          </label>
        </div>
        <p class="text-xs text-slate-500">
          The URL is reached from the TaleWeaver backend. Private/LAN endpoints require
          ALLOW_PRIVATE_NETWORK_MODELS=true. One track renders at a time.
        </p>
      </section>

      <section class="space-y-3 rounded-3xl border border-slate-800 bg-slate-900 p-6">
        <h3 class="font-bold text-white">Test run</h3>
        <p class="text-xs text-slate-500">Renders one clip with the saved workflow. Save your changes first.</p>
        <textarea v-model="testPrompt" rows="2" maxlength="1000"
          class="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-sm text-white"></textarea>
        <div class="flex flex-wrap items-center gap-4">
          <button
            type="button"
            :disabled="isTesting || !settings.has_workflow || !testPrompt.trim()"
            class="rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold uppercase tracking-wider text-white hover:bg-amber-500 disabled:opacity-50"
            @click="runTest"
          >
            {{ isTesting ? 'Composing…' : 'Generate test clip' }}
          </button>
          <audio v-if="testUrl" :src="testUrl" controls class="h-9"></audio>
        </div>
      </section>
    </div>
  </div>
</template>
