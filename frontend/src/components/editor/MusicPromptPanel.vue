<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Sparkles, Music, Trash2, Save } from 'lucide-vue-next'
import { editorMusicService, type MusicJob, type MusicTarget } from '@/services/editorMusicService'
import { notificationService } from '@/services/notificationService'

const props = defineProps<{
  adventureId: string
  targetType: 'scene' | 'theme'
  targetId?: string | null
  prompt?: string | null
  musicUrl?: string | null
  /** Theme only: the author switch for scene and theme music. */
  musicEnabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const POLL_MS = 2000

const draft = ref(props.prompt || '')
const duration = ref<number | null>(null)
const isSuggesting = ref(false)
const isSaving = ref(false)
const job = ref<MusicJob | null>(null)
const error = ref('')
let pollTimer: ReturnType<typeof setInterval> | undefined

const target = computed((): MusicTarget => ({ target_type: props.targetType, target_id: props.targetId ?? null }))
const isGenerating = computed((): boolean => job.value?.status === 'running')
const promptChanged = computed((): boolean => draft.value.trim() !== (props.prompt || '').trim())
const title = computed((): string => (props.targetType === 'scene' ? 'Scene Music' : 'Main Theme Music'))
const hint = computed((): string =>
  props.targetType === 'scene'
    ? 'Loops while the player is in this scene. Scenes without music play the main theme (Tone tab).'
    : 'Plays in every scene without its own music. Scripts (tw.music) can override both.',
)

watch(
  () => [props.prompt, props.targetId],
  () => {
    if (!isGenerating.value) draft.value = props.prompt || ''
  },
)

function report(err: unknown): void {
  error.value = err instanceof Error ? err.message : String(err)
  notificationService.add(error.value, 'error')
}

async function suggest(): Promise<void> {
  isSuggesting.value = true
  error.value = ''
  try {
    const suggested = await editorMusicService.suggestPrompt(props.adventureId, target.value)
    if (suggested) draft.value = suggested
  } catch (err) {
    report(err)
  } finally {
    isSuggesting.value = false
  }
}

async function savePrompt(): Promise<void> {
  isSaving.value = true
  try {
    await editorMusicService.savePrompt(props.adventureId, target.value, draft.value)
    emit('refresh')
  } catch (err) {
    report(err)
  } finally {
    isSaving.value = false
  }
}

function stopPolling(): void {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = undefined
}

async function poll(jobId: string): Promise<void> {
  try {
    const current = await editorMusicService.jobStatus(props.adventureId, jobId)
    job.value = current
    if (current.status === 'running') return
    stopPolling()
    if (current.status === 'failed') {
      report(new Error(current.error || 'Music generation failed.'))
      return
    }
    notificationService.add(`${title.value} rendered in ${current.elapsed} s.`, 'success')
    emit('refresh')
  } catch (err) {
    // A single slow poll is not fatal; a lost job (server restart) is.
    if (err instanceof Error && err.message.includes('not found')) {
      stopPolling()
      job.value = null
      report(err)
    }
  }
}

async function generate(): Promise<void> {
  error.value = ''
  try {
    job.value = await editorMusicService.generate(
      props.adventureId,
      target.value,
      draft.value,
      duration.value || undefined,
    )
    stopPolling()
    pollTimer = setInterval(() => poll(job.value!.id), POLL_MS)
  } catch (err) {
    report(err)
  }
}

async function remove(): Promise<void> {
  try {
    await editorMusicService.remove(props.adventureId, target.value)
    emit('refresh')
  } catch (err) {
    report(err)
  }
}

async function toggleEnabled(event: Event): Promise<void> {
  try {
    await editorMusicService.setEnabled(props.adventureId, (event.target as HTMLInputElement).checked)
    emit('refresh')
  } catch (err) {
    report(err)
  }
}

onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <label class="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">
        <Music class="w-3.5 h-3.5 text-orange-400" /> {{ title }}
        <span class="normal-case tracking-normal font-bold text-amber-400/80">Experimental</span>
      </label>
      <div class="flex items-center gap-2">
        <label v-if="targetType === 'theme'" class="flex items-center gap-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          <input type="checkbox" :checked="musicEnabled !== false" class="accent-orange-500" @change="toggleEnabled" />
          Scene &amp; theme music on
        </label>
        <button
          type="button"
          :disabled="isSuggesting || isGenerating"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-300 text-[9px] font-black uppercase tracking-widest transition-all hover:bg-cyan-500/20 disabled:opacity-40"
          title="Let the Simple LLM write a prompt from the adventure tone and this description (always loopable)"
          @click="suggest"
        >
          <Sparkles :class="['w-3 h-3', isSuggesting ? 'animate-spin' : '']" />
          {{ isSuggesting ? 'Thinking...' : 'AI Prompt' }}
        </button>
      </div>
    </div>

    <div class="bg-slate-950/30 border border-white/5 rounded-xl p-4 space-y-3 shadow-inner">
      <textarea
        v-model="draft"
        rows="3"
        maxlength="1000"
        :disabled="isGenerating"
        placeholder="e.g. slow dark ambient, low cello drones, distant choir, dripping water, 60 bpm. Seamless loop: no intro, no fade-out ending."
        class="w-full bg-slate-950/80 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50 placeholder-slate-600"
      ></textarea>
      <p class="text-[10px] text-slate-500">
        {{ hint }} Describe the sound (genre, instruments, tempo, mood), not the scene. Instrumental only; no artist names.
      </p>

      <div class="flex flex-wrap items-center gap-3">
        <button
          type="button"
          :disabled="isGenerating || !draft.trim()"
          class="px-4 py-2 bg-orange-600 hover:bg-orange-500 disabled:opacity-40 text-white font-black text-[10px] uppercase tracking-wider rounded-xl transition-all"
          @click="generate"
        >
          {{ isGenerating ? `Composing… ${job?.elapsed ?? 0} s` : musicUrl ? 'Regenerate Music' : 'Generate Music' }}
        </button>
        <button
          v-if="promptChanged && !isGenerating"
          type="button"
          :disabled="isSaving"
          class="inline-flex items-center gap-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-black text-[10px] uppercase tracking-wider rounded-xl"
          title="Save the prompt without rendering"
          @click="savePrompt"
        >
          <Save class="w-3 h-3" /> Save Prompt
        </button>
        <label class="flex items-center gap-1.5 text-[10px] text-slate-400">
          Length (s)
          <input v-model.number="duration" type="number" min="5" max="600" placeholder="auto"
            class="w-16 bg-slate-950/80 border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200" />
        </label>
        <template v-if="musicUrl">
          <audio :src="musicUrl" controls loop class="h-8 max-w-full"></audio>
          <button type="button" class="p-1.5 text-slate-500 hover:text-red-400" title="Delete the rendered music" @click="remove">
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </template>
      </div>
      <p v-if="error" class="text-[10px] text-rose-400">{{ error }}</p>
    </div>
  </div>
</template>
