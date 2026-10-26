<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { Play, Square } from 'lucide-vue-next'
import { audioService } from '@/services/audioService'
import type { TtsVoice, TtsVoiceList } from '@/types'

const props = defineProps<{
  modelValue?: string
  voiceList: TtsVoiceList | null
  npcName?: string
  adventureId?: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const previewError = ref('')
const isPreviewing = ref(false)

const voices = computed(() => props.voiceList?.voices ?? [])
const supportsNpcVoices = computed(() => Boolean(props.voiceList?.supports_npc_voices))

const selected = computed({
  get: () => props.modelValue || '',
  set: (value: string) => emit('update:modelValue', value),
})

const selectedVoice = computed(() => voices.value.find((voice) => voice.id === selected.value))
const previewTitle = computed(() => {
  if (isPreviewing.value) return 'Stop preview'
  if (!supportsNpcVoices.value) return 'Previews need ElevenLabs as speech provider'
  return selectedVoice.value ? 'Preview this voice' : 'Pick a voice to preview it'
})
// A stored voice that was removed from the voice list: the game uses the narrator voice.
const isMissingVoice = computed(() => Boolean(selected.value) && !selectedVoice.value)

function voiceLabel(voice: TtsVoice): string {
  const details = [voice.gender, voice.age, voice.accent, voice.description].filter(Boolean).join(', ')
  return details ? `${voice.name} — ${details}` : voice.name
}

function stopPreview(): void {
  audioService.stop()
  isPreviewing.value = false
}

async function playSample(voice: TtsVoice | undefined): Promise<void> {
  audioService.unlock()
  const name = props.npcName?.trim() || 'a stranger'
  await audioService.speak(`Well met, traveler. They call me ${name}. What brings you here?`, {
    voiceOverride: voice?.id,
    adventureId: props.adventureId,
  })
  if (audioService.lastError.value) throw new Error(audioService.lastError.value)
}

async function togglePreview(): Promise<void> {
  if (isPreviewing.value) {
    stopPreview()
    return
  }
  previewError.value = ''
  isPreviewing.value = true
  try {
    await playSample(selectedVoice.value)
  } catch (err) {
    previewError.value = err instanceof Error ? err.message : String(err)
  } finally {
    isPreviewing.value = false
  }
}

onBeforeUnmount(stopPreview)
</script>

<template>
  <div class="space-y-3">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Voice</label>

    <p v-if="!voices.length" class="text-[11px] leading-snug text-slate-500">
      The voice list is empty or could not be loaded.
    </p>

    <template v-else>
      <div class="flex gap-2">
        <select
          v-model="selected"
          class="min-w-0 flex-1 bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-slate-300 focus:border-emerald-500 outline-none transition-all"
        >
          <option value="">Automatic (cast from description)</option>
          <option v-if="isMissingVoice" :value="selected">Removed voice (uses the narrator voice)</option>
          <option v-for="voice in voices" :key="voice.id" :value="voice.id">{{ voiceLabel(voice) }}</option>
        </select>
        <button
          type="button"
          class="shrink-0 flex items-center gap-2 px-3 py-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-[10px] font-black uppercase tracking-widest text-emerald-400 hover:bg-emerald-500/10 transition-all disabled:opacity-40"
          :disabled="(!selectedVoice || !supportsNpcVoices) && !isPreviewing"
          :title="previewTitle"
          @click="togglePreview"
        >
          <Square v-if="isPreviewing" class="w-3.5 h-3.5" />
          <Play v-else class="w-3.5 h-3.5" />
          <span>{{ isPreviewing ? 'Stop' : 'Preview' }}</span>
        </button>
      </div>
      <p class="text-[11px] leading-snug text-slate-500">
        <template v-if="isMissingVoice">This voice is no longer in the voice list, so the narrator voice is used. Pick a new one.</template>
        <template v-else-if="selectedVoice?.good_for.length">Good for: {{ selectedVoice.good_for.join(', ') }}.</template>
        <template v-else-if="!selectedVoice">The game picks a fitting voice from the voice list that differs from the narrator and other characters.</template>
      </p>
      <p v-if="!supportsNpcVoices" class="text-[11px] leading-snug text-amber-400/80">
        Character voices are spoken with ElevenLabs. With the current speech provider, all lines use the narrator
        voice; the choice made here takes effect once ElevenLabs is selected.
      </p>
      <p v-if="previewError" class="text-[11px] text-red-400">{{ previewError }}</p>
    </template>
  </div>
</template>
