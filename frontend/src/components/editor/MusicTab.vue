<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Music, Sparkles, Upload, Play, Pause, Trash2, RefreshCw, Pencil, Check, X } from 'lucide-vue-next'
import { editorMusicService, type MusicLibrary, type MusicTrack } from '@/services/editorMusicService'
import { notificationService } from '@/services/notificationService'

const props = defineProps<{
  adventureId: string
  scenes: { id: string; label?: string; name?: string }[]
}>()

const emit = defineEmits<{
  (e: 'refresh-world'): void
}>()

const POLL_MS = 2000

const library = ref<MusicLibrary | null>(null)
const isLoading = ref(false)

// Generate form
const genName = ref('')
const genReferenceScene = ref('')
const genPrompt = ref('')
const genDuration = ref<number | null>(null)
const isSuggesting = ref(false)
const isStarting = ref(false)

// Upload form
const uploadName = ref('')
const uploadFile = ref<File | null>(null)
const isUploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

// Table state
const editingId = ref('')
const editName = ref('')
const editPrompt = ref('')
const playingId = ref('')
let player: HTMLAudioElement | null = null
let pollTimer: ReturnType<typeof setInterval> | undefined

const tracks = computed((): MusicTrack[] => library.value?.tracks ?? [])
const generationOn = computed((): boolean => !!library.value?.generation.enabled)
const providerLabel = computed((): string =>
  library.value?.generation.provider === 'lyria' ? 'Google Lyria' : 'ComfyUI',
)
const sceneLabels = computed((): Record<string, string> =>
  Object.fromEntries(props.scenes.map((s) => [s.id, s.label || s.name || s.id])),
)
const hasRunningJob = computed((): boolean =>
  Object.values(library.value?.jobs ?? {}).some((job) => job.status === 'running'),
)

function report(err: unknown): void {
  notificationService.add(err instanceof Error ? err.message : String(err), 'error')
}

async function reload(): Promise<void> {
  try {
    const previous = library.value
    library.value = await editorMusicService.load(props.adventureId)
    announceFinishedJobs(previous)
    ensurePolling()
  } catch (err) {
    report(err)
  }
}

function announceFinishedJobs(previous: MusicLibrary | null): void {
  if (!previous || !library.value) return
  for (const [trackId, job] of Object.entries(library.value.jobs)) {
    if (previous.jobs[trackId]?.status !== 'running' || job.status === 'running') continue
    const name = library.value.tracks.find((t) => t.id === trackId)?.name || 'Track'
    if (job.status === 'done') notificationService.add(`${name} rendered in ${job.elapsed} s.`, 'success')
    else notificationService.add(`${name}: ${job.error || 'Music generation failed.'}`, 'error')
  }
}

function ensurePolling(): void {
  if (hasRunningJob.value && !pollTimer) {
    pollTimer = setInterval(reload, POLL_MS)
    return
  }
  if (!hasRunningJob.value && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
}

function trackStatus(track: MusicTrack): { label: string; tone: string } {
  const job = library.value?.jobs[track.id]
  if (job?.status === 'running') return { label: `Composing… ${job.elapsed} s`, tone: 'text-amber-300' }
  if (job?.status === 'failed' && !track.url) return { label: `Failed: ${job.error || ''}`, tone: 'text-rose-400' }
  if (track.url) return { label: 'Ready', tone: 'text-emerald-400' }
  return { label: 'No audio yet', tone: 'text-slate-500' }
}

function usedBy(track: MusicTrack): string {
  const ids = library.value?.scene_usage[track.id] ?? []
  return ids.map((id) => sceneLabels.value[id] || id).join(', ') || '—'
}

async function suggest(): Promise<void> {
  isSuggesting.value = true
  try {
    const prompt = await editorMusicService.suggestPrompt(props.adventureId, genReferenceScene.value || null)
    if (prompt) genPrompt.value = prompt
    if (!genName.value && genReferenceScene.value) genName.value = `${sceneLabels.value[genReferenceScene.value]} Theme`
  } catch (err) {
    report(err)
  } finally {
    isSuggesting.value = false
  }
}

async function generate(): Promise<void> {
  isStarting.value = true
  try {
    await editorMusicService.generate(props.adventureId, {
      name: genName.value,
      prompt: genPrompt.value,
      reference_scene_id: genReferenceScene.value || null,
      duration: genDuration.value,
    })
    genName.value = ''
    genPrompt.value = ''
    await reload()
  } catch (err) {
    report(err)
  } finally {
    isStarting.value = false
  }
}

function onFileChosen(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0] ?? null
  uploadFile.value = file
  if (file && !uploadName.value) uploadName.value = file.name.replace(/\.[^.]+$/, '')
}

async function upload(): Promise<void> {
  if (!uploadFile.value) return
  isUploading.value = true
  try {
    const track = await editorMusicService.upload(props.adventureId, uploadFile.value, uploadName.value)
    notificationService.add(`${track.name} added to the music library.`, 'success')
    uploadFile.value = null
    uploadName.value = ''
    if (fileInput.value) fileInput.value.value = ''
    await reload()
  } catch (err) {
    report(err)
  } finally {
    isUploading.value = false
  }
}

async function rerender(track: MusicTrack): Promise<void> {
  try {
    await editorMusicService.render(props.adventureId, track.id)
    await reload()
  } catch (err) {
    report(err)
  }
}

function startEdit(track: MusicTrack): void {
  editingId.value = track.id
  editName.value = track.name
  editPrompt.value = track.prompt
}

async function saveEdit(track: MusicTrack): Promise<void> {
  try {
    await editorMusicService.update(props.adventureId, track.id, { name: editName.value, prompt: editPrompt.value })
    editingId.value = ''
    await reload()
  } catch (err) {
    report(err)
  }
}

async function remove(track: MusicTrack): Promise<void> {
  const scenes = library.value?.scene_usage[track.id]?.length ?? 0
  const note = scenes ? ` ${scenes} scene(s) using it become silent.` : ''
  if (!window.confirm(`Delete "${track.name}"?${note}`)) return
  try {
    if (playingId.value === track.id) stopPlayer()
    library.value = await editorMusicService.remove(props.adventureId, track.id)
    emit('refresh-world')
  } catch (err) {
    report(err)
  }
}

async function toggleEnabled(event: Event): Promise<void> {
  try {
    await editorMusicService.setEnabled(props.adventureId, (event.target as HTMLInputElement).checked)
    await reload()
  } catch (err) {
    report(err)
  }
}

function stopPlayer(): void {
  player?.pause()
  player = null
  playingId.value = ''
}

function togglePlay(track: MusicTrack): void {
  if (playingId.value === track.id) {
    stopPlayer()
    return
  }
  stopPlayer()
  if (!track.url) return
  player = new Audio(track.url)
  player.loop = true
  player.play().catch(report)
  playingId.value = track.id
}

onMounted(async (): Promise<void> => {
  isLoading.value = true
  await reload()
  isLoading.value = false
})

onBeforeUnmount((): void => {
  stopPlayer()
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <section class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-slate-900/40 p-5 sm:p-6 rounded-2xl border border-white/5 shadow-xl">
      <div class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center border border-orange-500/20">
          <Music class="w-5 h-5 text-orange-400" />
        </div>
        <div>
          <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Music Library <span class="ml-1 normal-case tracking-normal text-[10px] text-amber-400">Experimental</span></h3>
          <p class="text-xs text-slate-500">
            Tracks of this adventure. Each scene picks one in its scene dialog; walking between scenes with
            the same track keeps it playing, a scene without a track fades the music out.
          </p>
        </div>
      </div>
      <label v-if="library" class="flex items-center gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider shrink-0">
        <input type="checkbox" :checked="library.music_enabled" class="accent-orange-500" @change="toggleEnabled" />
        Scene music on
      </label>
    </section>

    <div class="grid gap-6 lg:grid-cols-2">
      <!-- Generate -->
      <section class="space-y-3 bg-slate-900/40 p-5 rounded-2xl border border-white/5">
        <h4 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Generate</h4>
        <p v-if="library && !generationOn" class="text-[11px] text-amber-400">
          Music generation is switched off. An admin turns it on under Admin → Music.
        </p>
        <div class="grid gap-3 sm:grid-cols-2">
          <input v-model="genName" maxlength="100" placeholder="Track name (e.g. Crypt Theme)"
            class="bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50" />
          <select v-model="genReferenceScene"
            class="bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50"
            title="The AI prompt is written from this scene and the adventure's tone">
            <option value="">Reference: whole adventure</option>
            <option v-for="scene in scenes" :key="scene.id" :value="scene.id">Reference: {{ scene.label || scene.name || scene.id }}</option>
          </select>
        </div>
        <div class="relative">
          <textarea v-model="genPrompt" rows="4" maxlength="1000"
            placeholder="Describe the sound: genre, instruments, tempo, mood. e.g. slow dark ambient, low cello drones, distant choir, 60 bpm. Seamless loop: no intro, no fade-out ending."
            class="w-full bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50 placeholder-slate-600"></textarea>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <button type="button" :disabled="isSuggesting"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-cyan-400/20 bg-cyan-500/10 text-cyan-300 text-[10px] font-black uppercase tracking-widest hover:bg-cyan-500/20 disabled:opacity-40"
            title="The Simple LLM writes a prompt from the tone and the reference scene; it always asks for a seamless loop"
            @click="suggest">
            <Sparkles :class="['w-3 h-3', isSuggesting ? 'animate-spin' : '']" />
            {{ isSuggesting ? 'Thinking...' : 'AI Prompt' }}
          </button>
          <label class="flex items-center gap-1.5 text-[10px] text-slate-400">
            Length (s)
            <input v-model.number="genDuration" type="number" min="5" max="600" placeholder="auto"
              class="w-16 bg-slate-950/80 border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200" />
          </label>
          <button type="button" :disabled="isStarting || !genPrompt.trim() || !generationOn"
            class="ml-auto px-4 py-2 bg-orange-600 hover:bg-orange-500 disabled:opacity-40 text-white font-black text-[10px] uppercase tracking-wider rounded-xl"
            @click="generate">
            {{ isStarting ? 'Starting...' : `Generate (${providerLabel})` }}
          </button>
        </div>
        <p class="text-[10px] text-slate-500">Instrumental only; music models block artist names and lyrics.</p>
      </section>

      <!-- Upload -->
      <section class="space-y-3 bg-slate-900/40 p-5 rounded-2xl border border-white/5">
        <h4 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Upload</h4>
        <input v-model="uploadName" maxlength="100" placeholder="Track name"
          class="w-full bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50" />
        <div class="flex flex-wrap items-center gap-3">
          <input ref="fileInput" type="file" accept="audio/mpeg,audio/wav,audio/ogg,audio/flac,audio/mp4,.mp3,.wav,.ogg,.opus,.flac,.m4a"
            class="text-xs text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:font-bold file:text-slate-200"
            @change="onFileChosen" />
          <button type="button" :disabled="isUploading || !uploadFile"
            class="ml-auto inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-black text-[10px] uppercase tracking-wider rounded-xl"
            @click="upload">
            <Upload class="w-3 h-3" /> {{ isUploading ? 'Uploading...' : 'Upload' }}
          </button>
        </div>
        <p class="text-[10px] text-slate-500">MP3, WAV, OGG/Opus, FLAC or M4A, up to 50 MB. Only use music you may share with this adventure.</p>
      </section>
    </div>

    <!-- Track table -->
    <section class="bg-slate-900/40 rounded-2xl border border-white/5 overflow-x-auto">
      <table class="w-full text-xs text-slate-300">
        <thead class="text-[10px] uppercase tracking-widest text-slate-500 border-b border-white/5">
          <tr>
            <th class="p-3 w-10"></th>
            <th class="p-3 text-left">Track</th>
            <th class="p-3 text-left">Source</th>
            <th class="p-3 text-left">Scenes</th>
            <th class="p-3 text-left">Status</th>
            <th class="p-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!isLoading && !tracks.length">
            <td colspan="6" class="p-6 text-center text-slate-500 italic">No tracks yet. Generate or upload one above.</td>
          </tr>
          <tr v-for="track in tracks" :key="track.id" class="border-b border-white/5 last:border-0 align-top">
            <td class="p-3">
              <button type="button" :disabled="!track.url"
                class="p-1.5 rounded-lg bg-slate-800 text-slate-200 hover:bg-orange-600 disabled:opacity-30"
                :title="playingId === track.id ? 'Stop' : 'Play'" @click="togglePlay(track)">
                <Pause v-if="playingId === track.id" class="w-3.5 h-3.5" />
                <Play v-else class="w-3.5 h-3.5" />
              </button>
            </td>
            <td class="p-3 min-w-[16rem]">
              <template v-if="editingId === track.id">
                <input v-model="editName" maxlength="100"
                  class="w-full mb-2 bg-slate-950/80 border border-orange-500/40 rounded-lg px-2 py-1 text-xs text-white" />
                <textarea v-model="editPrompt" rows="3" maxlength="1000" placeholder="Prompt (needed to render again)"
                  class="w-full bg-slate-950/80 border border-orange-500/40 rounded-lg px-2 py-1 text-[11px] text-slate-200"></textarea>
              </template>
              <template v-else>
                <div class="font-bold text-white">{{ track.name }}</div>
                <div v-if="track.prompt" class="text-[11px] text-slate-500 line-clamp-2" :title="track.prompt">{{ track.prompt }}</div>
                <div v-if="track.reference_scene_id" class="text-[10px] text-slate-600">Reference: {{ sceneLabels[track.reference_scene_id] || track.reference_scene_id }}</div>
              </template>
            </td>
            <td class="p-3 capitalize">{{ track.source }}</td>
            <td class="p-3 text-[11px]">{{ usedBy(track) }}</td>
            <td class="p-3 text-[11px]" :class="trackStatus(track).tone">{{ trackStatus(track).label }}</td>
            <td class="p-3">
              <div class="flex justify-end gap-1">
                <template v-if="editingId === track.id">
                  <button type="button" class="p-1.5 text-emerald-400 hover:text-emerald-300" title="Save" @click="saveEdit(track)"><Check class="w-4 h-4" /></button>
                  <button type="button" class="p-1.5 text-slate-400 hover:text-white" title="Cancel" @click="editingId = ''"><X class="w-4 h-4" /></button>
                </template>
                <template v-else>
                  <button type="button" class="p-1.5 text-slate-400 hover:text-white" title="Rename / edit prompt" @click="startEdit(track)"><Pencil class="w-3.5 h-3.5" /></button>
                  <button v-if="track.prompt" type="button" :disabled="!generationOn || trackStatus(track).label.startsWith('Composing')"
                    class="p-1.5 text-slate-400 hover:text-orange-300 disabled:opacity-30"
                    :title="track.url ? 'Render again from the prompt' : 'Render from the prompt'" @click="rerender(track)">
                    <RefreshCw class="w-3.5 h-3.5" />
                  </button>
                  <button type="button" class="p-1.5 text-slate-400 hover:text-red-400" title="Delete" @click="remove(track)"><Trash2 class="w-3.5 h-3.5" /></button>
                </template>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
