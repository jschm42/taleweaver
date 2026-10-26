<script setup lang="ts">
import { computed, ref } from 'vue'
import { Play, Square } from 'lucide-vue-next'
import { audioService } from '@/services/audioService'

type VoiceOption = { name: string; gender?: string; description?: string }

const props = defineProps<{
  modelValue?: string
  voices: VoiceOption[]
  npcName?: string
  adventureId?: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const previewError = ref('')
const isPreviewing = computed(() => audioService.isPlaying.value || audioService.isGenerating.value)

const selected = computed({
  get: () => props.modelValue || '',
  set: (value: string) => emit('update:modelValue', value),
})

const selectedVoice = computed(() => props.voices.find((voice) => voice.name === selected.value))

function voiceLabel(voice: VoiceOption): string {
  const details = [voice.gender, voice.description].filter(Boolean).join(', ')
  return details ? `${voice.name} — ${details}` : voice.name
}

async function togglePreview(): Promise<void> {
  if (isPreviewing.value) {
    audioService.stop()
    return
  }
  previewError.value = ''
  audioService.unlock()
  const name = props.npcName?.trim() || 'a stranger'
  try {
    await audioService.speak(`Well met, traveler. They call me ${name}. What brings you here?`, {
      voiceOverride: selected.value || undefined,
      adventureId: props.adventureId,
      useTextChunking: false,
    })
  } catch (err) {
    previewError.value = err instanceof Error ? err.message : String(err)
  }
  if (audioService.lastError.value) previewError.value = audioService.lastError.value
}
</script>

<template>
  <div class="space-y-3">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Voice</label>
    <div class="flex gap-2">
      <select
        v-model="selected"
        class="min-w-0 flex-1 bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-slate-300 focus:border-emerald-500 outline-none transition-all"
      >
        <option value="">Automatic (cast from description)</option>
        <option v-for="voice in voices" :key="voice.name" :value="voice.name">{{ voiceLabel(voice) }}</option>
      </select>
      <button
        type="button"
        class="shrink-0 flex items-center gap-2 px-3 py-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-[10px] font-black uppercase tracking-widest text-emerald-400 hover:bg-emerald-500/10 transition-all"
        :title="isPreviewing ? 'Stop preview' : 'Preview this voice'"
        @click="togglePreview"
      >
        <Square v-if="isPreviewing" class="w-3.5 h-3.5" />
        <Play v-else class="w-3.5 h-3.5" />
        <span>{{ isPreviewing ? 'Stop' : 'Preview' }}</span>
      </button>
    </div>
    <p class="text-[11px] leading-snug text-slate-500">
      <template v-if="selectedVoice">Used for this character's lines when speech output is on.</template>
      <template v-else>The game picks a fitting voice that differs from the narrator and other characters. Preview plays the narrator voice.</template>
    </p>
    <p v-if="previewError" class="text-[11px] text-red-400">{{ previewError }}</p>
  </div>
</template>
