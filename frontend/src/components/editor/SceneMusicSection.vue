<script setup lang="ts">
/**
 * SceneMusicSection — Background music of a scene in the editor: upload an audio file,
 * set or clear the music URL, and test-play the track.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Music, Play, Square, Trash2, Upload } from 'lucide-vue-next'
import { entityService } from '@/services/entityService'
import { visualService } from '@/services/visualService'
import { notificationService } from '@/services/notificationService'
import { musicService } from '@/services/musicService'

const ACCEPTED_AUDIO = '.mp3,.ogg,.wav,audio/mpeg,audio/ogg,audio/wav'

const props = defineProps<{
  adventureId: string
  sceneId: string
  musicUrl?: string | null
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const urlInput = ref(props.musicUrl || '')
const isSaving = ref(false)
const isUploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.musicUrl,
  (url) => {
    urlInput.value = url || ''
  },
)

const currentUrl = computed(() => String(props.musicUrl || ''))
const isPreviewing = computed(() => !!currentUrl.value && musicService.previewPlayingUrl.value === currentUrl.value)
const fileName = computed(() => currentUrl.value.split('/').pop() || '')
const isBusy = computed(() => isSaving.value || isUploading.value)
const urlChanged = computed(() => urlInput.value.trim() !== currentUrl.value)

async function saveMusicUrl(value: string): Promise<void> {
  isSaving.value = true
  try {
    if (isPreviewing.value) musicService.stopPreview()
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: props.sceneId,
      music_url: value,
    })
    notificationService.add(value ? 'Scene music updated.' : 'Scene music removed.', 'success')
    emit('refresh')
  } catch (error: unknown) {
    notificationService.add((error as Error)?.message || 'Failed to save scene music.', 'error')
  } finally {
    isSaving.value = false
  }
}

async function onFileSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  isUploading.value = true
  try {
    if (isPreviewing.value) musicService.stopPreview()
    await visualService.uploadSceneMusic(props.adventureId, props.sceneId, file)
    notificationService.add('Scene music uploaded.', 'success')
    emit('refresh')
  } catch (error: unknown) {
    notificationService.add((error as Error)?.message || 'Music upload failed.', 'error')
  } finally {
    isUploading.value = false
  }
}

function togglePreview(): void {
  if (isPreviewing.value) {
    musicService.stopPreview()
    return
  }
  if (currentUrl.value) void musicService.playPreview(currentUrl.value)
}

onBeforeUnmount(() => {
  if (isPreviewing.value) musicService.stopPreview()
})
</script>

<template>
  <div class="space-y-2">
    <div class="flex flex-wrap justify-between items-center gap-2">
      <label class="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Scene Music</label>
      <span class="text-[9px] text-slate-400 font-medium hidden sm:inline">Loops while the player is in this scene</span>
    </div>
    <div class="bg-slate-950/30 border border-white/5 rounded-xl p-4 space-y-3 shadow-inner">
      <div class="flex flex-wrap items-center gap-2">
        <Music class="w-4 h-4 shrink-0" :class="currentUrl ? 'text-emerald-400' : 'text-slate-600'" />
        <span v-if="currentUrl" class="flex-1 min-w-0 truncate text-xs text-slate-300 font-mono" :title="currentUrl">{{ fileName }}</span>
        <span v-else class="flex-1 text-xs text-slate-500 italic">No music configured. The scene plays in silence.</span>

        <button
          type="button"
          :disabled="!currentUrl"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[9px] font-black uppercase tracking-widest transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          :class="isPreviewing ? 'border-amber-400/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20' : 'border-emerald-400/20 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'"
          :title="currentUrl ? '' : 'Upload or enter a music file first'"
          @click="togglePreview"
        >
          <Square v-if="isPreviewing" class="w-3 h-3" />
          <Play v-else class="w-3 h-3" />
          {{ isPreviewing ? 'Stop Preview' : 'Test Play' }}
        </button>
        <button
          type="button"
          :disabled="isBusy"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-300 text-[9px] font-black uppercase tracking-widest transition-all hover:bg-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          title="Upload an .mp3, .ogg or .wav file (max 25 MB)"
          @click="fileInputRef?.click()"
        >
          <Upload :class="['w-3 h-3', isUploading ? 'animate-pulse' : '']" />
          {{ isUploading ? 'Uploading...' : 'Upload' }}
        </button>
        <button
          v-if="currentUrl"
          type="button"
          :disabled="isBusy"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-red-400/20 bg-red-500/10 text-red-300 text-[9px] font-black uppercase tracking-widest transition-all hover:bg-red-500/20 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          title="Remove the music from this scene"
          @click="saveMusicUrl('')"
        >
          <Trash2 class="w-3 h-3" />
          Remove
        </button>
        <input ref="fileInputRef" type="file" :accept="ACCEPTED_AUDIO" class="hidden" @change="onFileSelected" />
      </div>

      <div class="flex gap-2 items-center">
        <input
          v-model="urlInput"
          type="text"
          maxlength="500"
          placeholder="/data/adventures/library/.../audio/theme.mp3"
          class="flex-1 bg-slate-950/80 border border-white/10 rounded-xl px-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50 focus:ring-2 ring-emerald-500/10 placeholder-slate-600 transition-all font-mono"
          @keydown.enter="urlChanged && saveMusicUrl(urlInput.trim())"
        />
        <button
          type="button"
          :disabled="!urlChanged || isBusy"
          class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white font-black text-[10px] uppercase tracking-wider rounded-xl transition-all shadow-md shrink-0 cursor-pointer disabled:cursor-not-allowed"
          @click="saveMusicUrl(urlInput.trim())"
        >
          Save URL
        </button>
      </div>
    </div>
  </div>
</template>
