<script setup lang="ts">
/** Modal: compose a new library track from a prompt (optionally suggested from a reference scene). */
import { ref, watch } from 'vue'
import { Sparkles, X } from 'lucide-vue-next'
import { editorMusicService } from '@/services/editorMusicService'
import { notificationService } from '@/services/notificationService'
import SceneReferencePicker, { type ReferenceScene } from './SceneReferencePicker.vue'

export interface GenerateDraft {
  name?: string
  prompt?: string
  reference_scene_id?: string | null
}

const props = defineProps<{
  show: boolean
  adventureId: string
  scenes: ReferenceScene[]
  generationOn: boolean
  providerLabel: string
  /** Prefill, e.g. "Generate variant" of an existing track. */
  draft?: GenerateDraft | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'started'): void
}>()

const name = ref('')
const referenceScene = ref('')
const prompt = ref('')
const duration = ref<number | null>(null)
const isSuggesting = ref(false)
const isStarting = ref(false)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    name.value = props.draft?.name ?? ''
    prompt.value = props.draft?.prompt ?? ''
    referenceScene.value = props.draft?.reference_scene_id ?? ''
    duration.value = null
  },
)

function sceneLabel(id: string): string {
  const scene = props.scenes.find((s) => s.id === id)
  return scene ? scene.label || scene.name || scene.id : id
}

function report(err: unknown): void {
  notificationService.add(err instanceof Error ? err.message : String(err), 'error')
}

async function suggest(): Promise<void> {
  isSuggesting.value = true
  try {
    const suggested = await editorMusicService.suggestPrompt(props.adventureId, referenceScene.value || null)
    if (suggested) prompt.value = suggested
    if (!name.value && referenceScene.value) name.value = `${sceneLabel(referenceScene.value)} Theme`
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
      name: name.value,
      prompt: prompt.value,
      reference_scene_id: referenceScene.value || null,
      duration: duration.value,
    })
    emit('started')
    emit('close')
  } catch (err) {
    report(err)
  } finally {
    isStarting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6 backdrop-blur-xl bg-slate-950/60" @click.self="emit('close')">
        <div class="modal-content w-full max-w-xl bg-slate-900 border border-white/10 rounded-[2rem] shadow-2xl max-h-[92vh] flex flex-col" role="dialog" aria-modal="true" aria-label="Generate music track">
          <div class="flex items-center justify-between p-6 pb-4 border-b border-white/5">
            <div>
              <h3 class="text-xs font-black text-orange-400 uppercase tracking-widest">Generate Track</h3>
              <p class="text-[11px] text-slate-500">Rendered in the background with {{ providerLabel }}; you can keep working.</p>
            </div>
            <button type="button" class="text-slate-500 hover:text-white" aria-label="Close" @click="emit('close')"><X class="w-5 h-5" /></button>
          </div>

          <div class="p-6 space-y-4 overflow-y-auto">
            <p v-if="!generationOn" class="text-[11px] text-amber-400">
              Music generation is switched off. An admin turns it on under Admin → Music.
            </p>
            <label class="block space-y-1.5">
              <span class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Name</span>
              <input v-model="name" maxlength="100" placeholder="e.g. Crypt Theme"
                class="w-full bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50" />
            </label>
            <div class="space-y-1.5">
              <span class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Reference scene</span>
              <SceneReferencePicker v-model="referenceScene" :scenes="scenes" />
            </div>
            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Prompt</span>
                <button type="button" :disabled="isSuggesting"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-300 text-[9px] font-black uppercase tracking-widest hover:bg-cyan-500/20 disabled:opacity-40"
                  title="The Simple LLM writes a prompt from the tone and the reference scene; it always asks for a seamless loop"
                  @click="suggest">
                  <Sparkles :class="['w-3 h-3', isSuggesting ? 'animate-spin' : '']" />
                  {{ isSuggesting ? 'Thinking...' : 'AI Prompt' }}
                </button>
              </div>
              <textarea v-model="prompt" rows="5" maxlength="1000"
                placeholder="Describe the sound: genre, instruments, tempo, mood. e.g. slow dark ambient, low cello drones, distant choir, 60 bpm. Seamless loop: no intro, no fade-out ending."
                class="w-full bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50 placeholder-slate-600"></textarea>
              <p class="text-[10px] text-slate-500">Instrumental only; music models block artist names and lyrics.</p>
            </div>
            <label class="flex items-center gap-2 text-[10px] text-slate-400">
              Length (seconds)
              <input v-model.number="duration" type="number" min="5" max="600" placeholder="auto"
                class="w-20 bg-slate-950/80 border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200" />
            </label>
          </div>

          <div class="flex justify-end gap-2 p-6 pt-4 border-t border-white/5">
            <button type="button" class="px-4 py-2 text-[10px] font-black uppercase tracking-wider text-slate-400 hover:text-white" @click="emit('close')">Cancel</button>
            <button type="button" :disabled="isStarting || !prompt.trim() || !generationOn"
              class="px-5 py-2 bg-orange-600 hover:bg-orange-500 disabled:opacity-40 text-white font-black text-[10px] uppercase tracking-wider rounded-xl"
              @click="generate">
              {{ isStarting ? 'Starting...' : 'Generate' }}
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
