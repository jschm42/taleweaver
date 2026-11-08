<script setup lang="ts">
/** Modal: add an own audio file to the adventure's audio library (click or drop the file). */
import { computed, ref, watch } from 'vue'
import { Upload, X, FileAudio } from 'lucide-vue-next'
import { editorAudioService } from '@/services/editorAudioService'
import { notificationService } from '@/services/notificationService'
import { cleanTrackIdInput, suggestTrackId, trackIdError, TRACK_ID_MAX } from '@/utils/trackIds'

const props = defineProps<{
  show: boolean
  adventureId: string
  /** IDs already used in the library (the new ID must differ). */
  takenIds: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'uploaded'): void
}>()

const MAX_BYTES = 50 * 1024 * 1024

const name = ref('')
// The ID follows the file name until the author types one.
const typedId = ref('')
const idTouched = ref(false)
const trackId = computed((): string => {
  if (idTouched.value) return typedId.value
  const stem = file.value ? file.value.name.replace(/\.[^.]+$/, '') : name.value
  return suggestTrackId(stem, props.takenIds)
})
const idError = computed((): string => (file.value ? trackIdError(trackId.value, props.takenIds) : ''))

function onIdInput(event: Event): void {
  const input = event.target as HTMLInputElement
  typedId.value = cleanTrackIdInput(input.value)
  input.value = typedId.value
  idTouched.value = true
}
const file = ref<File | null>(null)
const isUploading = ref(false)
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    name.value = ''
    file.value = null
    typedId.value = ''
    idTouched.value = false
  },
)

function take(chosen: File | null | undefined): void {
  if (!chosen) return
  if (chosen.size > MAX_BYTES) {
    notificationService.add('The audio file is larger than 50 MB.', 'error')
    return
  }
  file.value = chosen
  if (!name.value) name.value = chosen.name.replace(/\.[^.]+$/, '')
}

function onDrop(event: DragEvent): void {
  isDragging.value = false
  take(event.dataTransfer?.files?.[0])
}

function sizeLabel(bytes: number): string {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`
}

async function upload(): Promise<void> {
  if (!file.value) return
  isUploading.value = true
  try {
    const track = await editorAudioService.upload(props.adventureId, file.value, name.value, trackId.value)
    notificationService.add(`${track.name} added to the audio library.`, 'success')
    emit('uploaded')
    emit('close')
  } catch (err) {
    notificationService.add(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    isUploading.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6 backdrop-blur-xl bg-slate-950/60" @click.self="emit('close')">
        <div class="modal-content w-full max-w-lg bg-slate-900 border border-white/10 rounded-[2rem] shadow-2xl max-h-[92vh] flex flex-col" role="dialog" aria-modal="true" aria-label="Upload audio track">
          <div class="flex items-center justify-between p-6 pb-4 border-b border-white/5">
            <div>
              <h3 class="text-xs font-black text-emerald-400 uppercase tracking-widest">Upload Track</h3>
              <p class="text-[11px] text-slate-500">MP3, WAV, OGG/Opus, FLAC or M4A, up to 50 MB.</p>
            </div>
            <button type="button" class="text-slate-500 hover:text-white" aria-label="Close" @click="emit('close')"><X class="w-5 h-5" /></button>
          </div>

          <div class="p-6 space-y-4">
            <button
              type="button"
              class="w-full rounded-2xl border-2 border-dashed px-4 py-8 text-center transition-colors"
              :class="isDragging ? 'border-emerald-400 bg-emerald-500/10' : 'border-white/10 hover:border-emerald-500/40 bg-slate-950/40'"
              @click="fileInput?.click()"
              @dragover.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @drop.prevent="onDrop"
            >
              <template v-if="file">
                <FileAudio class="w-6 h-6 mx-auto text-emerald-400" />
                <div class="mt-2 text-xs font-bold text-white truncate">{{ file.name }}</div>
                <div class="text-[10px] text-slate-500">{{ sizeLabel(file.size) }} · click to choose another file</div>
              </template>
              <template v-else>
                <Upload class="w-6 h-6 mx-auto text-slate-500" />
                <div class="mt-2 text-xs text-slate-300">Drop an audio file here or click to choose one</div>
              </template>
            </button>
            <input ref="fileInput" type="file" class="hidden"
              accept="audio/mpeg,audio/wav,audio/ogg,audio/flac,audio/mp4,.mp3,.wav,.ogg,.opus,.flac,.m4a"
              @change="take(($event.target as HTMLInputElement).files?.[0])" />
            <label class="block space-y-1.5">
              <span class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Name</span>
              <input v-model="name" maxlength="100" placeholder="Track name"
                class="w-full bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50" />
            </label>
            <label class="block space-y-1.5">
              <span class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Track ID</span>
              <input :value="trackId" :maxlength="TRACK_ID_MAX" spellcheck="false"
                class="w-full bg-slate-950/80 border rounded-xl px-3 py-2 font-mono text-xs text-slate-200 focus:outline-none"
                :class="idError ? 'border-rose-500/60' : 'border-white/10 focus:border-emerald-500/50'"
                @input="onIdInput" />
              <span class="block text-[10px]" :class="idError ? 'text-rose-400' : 'text-slate-500'">
                {{ idError || 'Suggested from the file name. Used by scripts (tw.audio.play) and blueprints (audio: ID).' }}
              </span>
            </label>
            <p class="text-[10px] text-slate-500">Only use audio you may share with this adventure; it is bundled in exports.</p>
          </div>

          <div class="flex justify-end gap-2 p-6 pt-4 border-t border-white/5">
            <button type="button" class="px-4 py-2 text-[10px] font-black uppercase tracking-wider text-slate-400 hover:text-white" @click="emit('close')">Cancel</button>
            <button type="button" :disabled="isUploading || !file || !!idError"
              class="inline-flex items-center gap-1.5 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-black text-[10px] uppercase tracking-wider rounded-xl"
              @click="upload">
              <Upload class="w-3 h-3" /> {{ isUploading ? 'Uploading...' : 'Upload' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
