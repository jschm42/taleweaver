<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Music, Play, Pause } from 'lucide-vue-next'
import { editorMusicService, type MusicTrack } from '@/services/editorMusicService'
import { notificationService } from '@/services/notificationService'

const props = defineProps<{
  adventureId: string
  sceneId: string
  trackId?: string | null
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'open-library'): void
}>()

const tracks = ref<MusicTrack[]>([])
const selected = ref(props.trackId || '')
const isSaving = ref(false)
const isPlaying = ref(false)
let player: HTMLAudioElement | null = null

const selectedTrack = computed((): MusicTrack | undefined => tracks.value.find((t) => t.id === selected.value))

watch(() => props.trackId, (value) => {
  selected.value = value || ''
})

function stop(): void {
  player?.pause()
  player = null
  isPlaying.value = false
}

function togglePreview(): void {
  if (isPlaying.value) {
    stop()
    return
  }
  if (!selectedTrack.value?.url) return
  player = new Audio(selectedTrack.value.url)
  player.loop = true
  player.play().catch(() => stop())
  isPlaying.value = true
}

async function choose(): Promise<void> {
  stop()
  isSaving.value = true
  try {
    await editorMusicService.setSceneTrack(props.adventureId, props.sceneId, selected.value || null)
    emit('refresh')
  } catch (err) {
    selected.value = props.trackId || ''
    notificationService.add(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    isSaving.value = false
  }
}

onMounted(async (): Promise<void> => {
  try {
    tracks.value = (await editorMusicService.load(props.adventureId)).tracks
  } catch (err) {
    notificationService.add(err instanceof Error ? err.message : String(err), 'error')
  }
})

onBeforeUnmount(stop)
</script>

<template>
  <div class="space-y-2">
    <label class="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">
      <Music class="w-3.5 h-3.5 text-orange-400" /> Scene Music
    </label>
    <div class="flex flex-wrap items-center gap-2 bg-slate-950/30 border border-white/5 rounded-xl p-3">
      <select v-model="selected" :disabled="isSaving"
        class="flex-1 min-w-[12rem] bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50"
        @change="choose">
        <option value="">No music (fades out the previous track)</option>
        <option v-for="track in tracks" :key="track.id" :value="track.id">
          {{ track.name }}{{ track.url ? '' : ' (no audio yet)' }}
        </option>
      </select>
      <button type="button" :disabled="!selectedTrack?.url"
        class="p-2 rounded-lg bg-slate-800 text-slate-200 hover:bg-orange-600 disabled:opacity-30"
        :title="isPlaying ? 'Stop preview' : 'Preview'" @click="togglePreview">
        <Pause v-if="isPlaying" class="w-3.5 h-3.5" />
        <Play v-else class="w-3.5 h-3.5" />
      </button>
      <button type="button" class="text-[10px] font-bold text-orange-300 hover:text-orange-200 uppercase tracking-wider" @click="emit('open-library')">
        Music Library →
      </button>
    </div>
    <p class="text-[10px] text-slate-500">
      Scenes with the same track keep it playing when the player walks between them; another track cross-fades.
    </p>
  </div>
</template>
