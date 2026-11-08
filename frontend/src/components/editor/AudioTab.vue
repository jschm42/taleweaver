<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { AudioLines, Sparkles, Upload, Play, Pause, Check, X, Star, Copy } from 'lucide-vue-next'
import { editorAudioService, type AudioLibrary, type AudioTrack } from '@/services/editorAudioService'
import { notificationService } from '@/services/notificationService'
import { cleanTrackIdInput, trackIdError, TRACK_ID_MAX } from '@/utils/trackIds'
import AudioGenerateModal, { type GenerateDraft } from '@/components/editor/audio/AudioGenerateModal.vue'
import AudioUploadModal from '@/components/editor/audio/AudioUploadModal.vue'
import AudioTrackMenu, { type TrackAction } from '@/components/editor/audio/AudioTrackMenu.vue'
import AudioDeleteModal from '@/components/editor/audio/AudioDeleteModal.vue'
import type { ReferenceScene } from '@/components/editor/audio/SceneReferencePicker.vue'

const props = defineProps<{
  adventureId: string
  scenes: ReferenceScene[]
}>()

const emit = defineEmits<{
  (e: 'refresh-world'): void
}>()

const POLL_MS = 2000

const library = ref<AudioLibrary | null>(null)
const isLoading = ref(false)

const showGenerate = ref(false)
const generateDraft = ref<GenerateDraft | null>(null)
const showUpload = ref(false)
const menu = ref<{ track: AudioTrack; x: number; y: number } | null>(null)
const deleting = ref<AudioTrack | null>(null)
const isDeleting = ref(false)

const editingId = ref('')
const editName = ref('')
const editId = ref('')
const takenIds = computed((): string[] => tracks.value.map((t) => t.id))
/** IDs of the other tracks (the edited one may keep its own). */
const otherIds = computed((): string[] => takenIds.value.filter((id) => id !== editingId.value))
const editIdError = computed((): string => {
  const current = tracks.value.find((t) => t.id === editingId.value)
  // An older id (random or longer) may stay as it is; a changed one must follow the rules.
  if (!editingId.value || editId.value === current?.id) return ''
  return trackIdError(editId.value, otherIds.value)
})
const editPrompt = ref('')
const playingId = ref('')
let player: HTMLAudioElement | null = null
let pollTimer: ReturnType<typeof setInterval> | undefined

const tracks = computed((): AudioTrack[] => library.value?.tracks ?? [])
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
    library.value = await editorAudioService.load(props.adventureId)
    announceFinishedJobs(previous)
    ensurePolling()
  } catch (err) {
    report(err)
  }
}

function announceFinishedJobs(previous: AudioLibrary | null): void {
  if (!previous || !library.value) return
  for (const [trackId, job] of Object.entries(library.value.jobs)) {
    if (previous.jobs[trackId]?.status !== 'running' || job.status === 'running') continue
    const name = library.value.tracks.find((t) => t.id === trackId)?.name || 'Track'
    if (job.status === 'done') notificationService.add(`${name} rendered in ${job.elapsed} s.`, 'success')
    else notificationService.add(`${name}: ${job.error || 'Audio generation failed.'}`, 'error')
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

function isRendering(track: AudioTrack): boolean {
  return library.value?.jobs[track.id]?.status === 'running'
}

function trackStatus(track: AudioTrack): { label: string; tone: string } {
  const job = library.value?.jobs[track.id]
  if (job?.status === 'running') return { label: `Composing… ${job.elapsed} s`, tone: 'text-amber-300' }
  if (job?.status === 'failed' && !track.url) return { label: `Failed: ${job.error || ''}`, tone: 'text-rose-400' }
  if (track.url) return { label: 'Ready', tone: 'text-emerald-400' }
  return { label: 'No audio yet', tone: 'text-slate-500' }
}

function usedBy(track: AudioTrack): string {
  const ids = library.value?.scene_usage[track.id] ?? []
  return ids.map((id) => sceneLabels.value[id] || id).join(', ') || '—'
}

// --- dialogs & menu -----------------------------------------------------------------------

function openGenerate(draft: GenerateDraft | null = null): void {
  generateDraft.value = draft
  showGenerate.value = true
}

function openMenu(track: AudioTrack, event: MouseEvent): void {
  menu.value = { track, x: event.clientX, y: event.clientY }
}

function openMenuFromButton(track: AudioTrack, event: MouseEvent): void {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  menu.value = { track, x: rect.right - 208, y: rect.bottom + 4 }
}

const actions: Record<TrackAction, (track: AudioTrack) => void> = {
  play: (track) => togglePlay(track),
  edit: (track) => startEdit(track),
  render: (track) => rerender(track),
  variant: (track) =>
    openGenerate({ name: `${track.name} (variant)`, prompt: track.prompt, reference_scene_id: track.reference_scene_id }),
  title: (track) => setTitle(library.value?.title_track_id === track.id ? null : track.id),
  download: (track) => download(track),
  delete: (track) => remove(track),
}

function onMenuAction(action: TrackAction): void {
  if (menu.value) actions[action](menu.value.track)
}

// --- track actions ------------------------------------------------------------------------

async function rerender(track: AudioTrack): Promise<void> {
  try {
    await editorAudioService.render(props.adventureId, track.id)
    await reload()
  } catch (err) {
    report(err)
  }
}

function startEdit(track: AudioTrack): void {
  editingId.value = track.id
  editId.value = track.id
  editName.value = track.name
  editPrompt.value = track.prompt
}

function onEditIdInput(event: Event): void {
  const input = event.target as HTMLInputElement
  editId.value = cleanTrackIdInput(input.value)
  input.value = editId.value
}

async function saveEdit(track: AudioTrack): Promise<void> {
  try {
    const changes: Partial<Pick<AudioTrack, 'id' | 'name' | 'prompt'>> = { name: editName.value, prompt: editPrompt.value }
    if (editId.value !== track.id) changes.id = editId.value
    await editorAudioService.update(props.adventureId, track.id, changes)
    if (changes.id) notificationService.add(`Track ID changed to ${changes.id}. Scenes and the title track follow; update scripts or blueprints that use '${track.id}'.`, 'info')
    editingId.value = ''
    await reload()
  } catch (err) {
    report(err)
  }
}

function remove(track: AudioTrack): void {
  deleting.value = track
}

function scenesUsing(track: AudioTrack): string[] {
  return (library.value?.scene_usage[track.id] ?? []).map((id) => sceneLabels.value[id] || id)
}

async function confirmDelete(): Promise<void> {
  const track = deleting.value
  if (!track) return
  isDeleting.value = true
  try {
    if (playingId.value === track.id) stopPlayer()
    library.value = await editorAudioService.remove(props.adventureId, track.id)
    emit('refresh-world')
    deleting.value = null
  } catch (err) {
    report(err)
  } finally {
    isDeleting.value = false
  }
}

async function setTitle(trackId: string | null): Promise<void> {
  try {
    await editorAudioService.setTitleTrack(props.adventureId, trackId)
    await reload()
  } catch (err) {
    report(err)
  }
}

async function copyId(track: AudioTrack): Promise<void> {
  try {
    await navigator.clipboard.writeText(track.id)
    notificationService.add(`Copied track ID ${track.id}.`, 'success')
  } catch {
    notificationService.add(`Copy failed. Track ID: ${track.id}`, 'info')
  }
}

function download(track: AudioTrack): void {
  if (!track.url) return
  const extension = track.url.split('?')[0].split('.').pop() || 'mp3'
  const base = track.name.replace(/[^\p{L}\p{N} _-]+/gu, '').trim().replace(/\s+/g, '_') || track.id
  const anchor = document.createElement('a')
  anchor.href = track.url
  anchor.download = `${base}.${extension}`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
}

async function toggleEnabled(event: Event): Promise<void> {
  try {
    await editorAudioService.setEnabled(props.adventureId, (event.target as HTMLInputElement).checked)
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

function togglePlay(track: AudioTrack): void {
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
    <!-- Header with the two entry points -->
    <section class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 bg-slate-900/40 p-5 sm:p-6 rounded-2xl border border-white/5 shadow-xl">
      <div class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center border border-orange-500/20 shrink-0">
          <AudioLines class="w-5 h-5 text-orange-400" />
        </div>
        <div>
          <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Audio Library <span class="ml-1 normal-case tracking-normal text-[10px] text-amber-400">Experimental</span></h3>
          <p class="text-xs text-slate-500">
            Tracks of this adventure. Each scene picks one in its scene dialog; walking between scenes with
            the same track keeps it playing, a scene without a track fades the audio out.
          </p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <label v-if="library" class="flex items-center gap-2 mr-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider"
          title="Played while the mouse is over this adventure's tile in the library. Without a title track the tile stays silent.">
          <Star class="w-3.5 h-3.5 text-amber-400" /> Title track
          <select :value="library.title_track_id || ''"
            class="normal-case tracking-normal font-normal bg-slate-950/80 border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200 max-w-[12rem]"
            @change="setTitle(($event.target as HTMLSelectElement).value || null)">
            <option value="">None</option>
            <option v-for="track in tracks" :key="track.id" :value="track.id">
              {{ track.name }}{{ track.url ? '' : ' (no audio yet)' }}
            </option>
          </select>
        </label>
        <label v-if="library" class="flex items-center gap-2 mr-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          <input type="checkbox" :checked="library.audio_enabled" class="accent-orange-500" @change="toggleEnabled" />
          Scene audio on
        </label>
        <button type="button"
          class="inline-flex items-center gap-1.5 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white font-black text-[10px] uppercase tracking-wider rounded-xl"
          :title="generationOn ? `Compose a track with ${providerLabel}` : 'Audio generation is switched off (Admin → Audio)'"
          @click="openGenerate()">
          <Sparkles class="w-3.5 h-3.5" /> Generate Track
        </button>
        <button type="button"
          class="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-black text-[10px] uppercase tracking-wider rounded-xl"
          @click="showUpload = true">
          <Upload class="w-3.5 h-3.5" /> Upload Track
        </button>
      </div>
    </section>

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
            <th class="p-3 w-10"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!isLoading && !tracks.length">
            <td colspan="6" class="p-8 text-center">
              <p class="text-slate-500 italic mb-3">No tracks yet.</p>
              <div class="flex justify-center gap-2">
                <button type="button" class="px-3 py-1.5 rounded-lg bg-orange-600/80 hover:bg-orange-500 text-white text-[10px] font-black uppercase tracking-wider" @click="openGenerate()">Generate Track</button>
                <button type="button" class="px-3 py-1.5 rounded-lg bg-emerald-600/80 hover:bg-emerald-500 text-white text-[10px] font-black uppercase tracking-wider" @click="showUpload = true">Upload Track</button>
              </div>
            </td>
          </tr>
          <tr
            v-for="track in tracks"
            :key="track.id"
            class="border-b border-white/5 last:border-0 align-top hover:bg-white/[0.02]"
            @contextmenu.prevent="openMenu(track, $event)"
          >
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
                <input v-model="editName" maxlength="100" aria-label="Track name"
                  class="w-full mb-2 bg-slate-950/80 border border-orange-500/40 rounded-lg px-2 py-1 text-xs text-white" />
                <input :value="editId" :maxlength="TRACK_ID_MAX" spellcheck="false" aria-label="Track ID"
                  class="w-full bg-slate-950/80 border rounded-lg px-2 py-1 font-mono text-[11px] text-slate-200"
                  :class="editIdError ? 'border-rose-500/60' : 'border-orange-500/40'"
                  @input="onEditIdInput" />
                <p class="mb-2 mt-0.5 text-[10px]" :class="editIdError ? 'text-rose-400' : 'text-slate-500'">
                  {{ editIdError || 'Track ID: letters, digits, underscores (max. 30).' }}
                </p>
                <textarea v-model="editPrompt" rows="3" maxlength="1000" placeholder="Prompt (needed to render again)"
                  class="w-full bg-slate-950/80 border border-orange-500/40 rounded-lg px-2 py-1 text-[11px] text-slate-200"></textarea>
                <div class="mt-1.5 flex gap-1">
                  <button type="button" :disabled="!!editIdError" class="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-600 text-white text-[10px] font-bold disabled:opacity-40" @click="saveEdit(track)"><Check class="w-3 h-3" /> Save</button>
                  <button type="button" class="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-800 text-slate-300 text-[10px] font-bold" @click="editingId = ''"><X class="w-3 h-3" /> Cancel</button>
                </div>
              </template>
              <template v-else>
                <div class="font-bold text-white flex items-center gap-2">
                  {{ track.name }}
                  <span v-if="library?.title_track_id === track.id"
                    class="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[9px] font-black uppercase tracking-wider text-amber-300"
                    title="Plays on the adventure's library tile">
                    <Star class="w-2.5 h-2.5" /> Title Track
                  </span>
                </div>
                <div class="mt-0.5 flex items-center gap-1.5">
                  <code class="rounded bg-slate-950/70 px-1.5 py-0.5 font-mono text-[10px] text-slate-400"
                    title="Track ID: use it in scripts (tw.audio.play), blueprints (audio: ID) and AI fixes">{{ track.id }}</code>
                  <button type="button" class="p-0.5 text-slate-500 hover:text-white" :aria-label="`Copy track ID ${track.id}`"
                    title="Copy track ID" @click.stop="copyId(track)">
                    <Copy class="w-3 h-3" />
                  </button>
                </div>
                <div v-if="track.prompt" class="text-[11px] text-slate-500 line-clamp-2" :title="track.prompt">{{ track.prompt }}</div>
                <div v-if="track.reference_scene_id" class="text-[10px] text-slate-600">Reference: {{ sceneLabels[track.reference_scene_id] || track.reference_scene_id }}</div>
              </template>
            </td>
            <td class="p-3 capitalize">{{ track.source }}</td>
            <td class="p-3 text-[11px]">{{ usedBy(track) }}</td>
            <td class="p-3 text-[11px]" :class="trackStatus(track).tone">{{ trackStatus(track).label }}</td>
            <td class="p-3">
              <button type="button" aria-label="Track actions" title="Actions (or right-click the row)"
                class="w-7 h-7 rounded-full bg-black/40 border border-white/10 flex items-center justify-center hover:bg-orange-500 transition-all"
                @click.stop="openMenuFromButton(track, $event)">
                <span class="flex flex-col gap-0.5">
                  <span class="w-0.5 h-0.5 bg-white rounded-full"></span>
                  <span class="w-0.5 h-0.5 bg-white rounded-full"></span>
                  <span class="w-0.5 h-0.5 bg-white rounded-full"></span>
                </span>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <AudioTrackMenu
      v-if="menu"
      :key="`${menu.track.id}-${menu.x}-${menu.y}`"
      :track="menu.track"
      :x="menu.x"
      :y="menu.y"
      :is-playing="playingId === menu.track.id"
      :is-rendering="isRendering(menu.track)"
      :generation-on="generationOn"
      :is-title="library?.title_track_id === menu.track.id"
      @action="onMenuAction"
      @close="menu = null"
    />

    <AudioGenerateModal
      :show="showGenerate"
      :adventure-id="adventureId"
      :scenes="scenes"
      :taken-ids="takenIds"
      :generation-on="generationOn"
      :provider-label="providerLabel"
      :draft="generateDraft"
      @close="showGenerate = false"
      @started="reload"
    />

    <AudioDeleteModal
      v-if="deleting"
      :track-name="deleting.name"
      :scenes="scenesUsing(deleting)"
      :is-deleting="isDeleting"
      @cancel="deleting = null"
      @confirm="confirmDelete"
    />

    <AudioUploadModal
      :show="showUpload"
      :adventure-id="adventureId"
      :taken-ids="takenIds"
      @close="showUpload = false"
      @uploaded="reload"
    />
  </div>
</template>
