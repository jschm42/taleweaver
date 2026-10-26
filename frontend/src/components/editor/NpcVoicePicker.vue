<script setup lang="ts">
/**
 * NpcVoicePicker — Voice of an NPC or the protagonist: automatic, a voice from the voice list
 * (backend/core/elevenlabs_voices.json) or an own ElevenLabs voice id, stored as "custom:<id>".
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Play, Square } from 'lucide-vue-next'
import { audioService } from '@/services/audioService'
import type { TtsVoice, TtsVoiceList } from '@/types'

const CUSTOM_PREFIX = 'custom:'
const CUSTOM_OPTION = '__custom__'
const VOICE_ID_PATTERN = /^[A-Za-z0-9]{20}$/

const props = defineProps<{
  modelValue?: string
  voiceList: TtsVoiceList | null
  npcName?: string
  adventureId?: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const previewError = ref('')
const previewHint = ref('')
const isPreviewing = ref(false)
const customId = ref('')
const isCustomChosen = ref(false)

const voices = computed(() => props.voiceList?.voices ?? [])
const supportsNpcVoices = computed(() => Boolean(props.voiceList?.supports_npc_voices))
const storedCustomId = computed(() =>
  (props.modelValue || '').startsWith(CUSTOM_PREFIX) ? (props.modelValue || '').slice(CUSTOM_PREFIX.length) : '',
)

const selectedVoice = computed(() => voices.value.find((voice) => voice.id === props.modelValue))
// A stored list voice that was removed from the voice list: the game uses the narrator voice.
const isMissingVoice = computed(() => Boolean(props.modelValue) && !selectedVoice.value && !storedCustomId.value)
const isCustom = computed(() => isCustomChosen.value || Boolean(storedCustomId.value))
const isCustomIdValid = computed(() => VOICE_ID_PATTERN.test(customId.value))
const previewVoiceId = computed(() => (isCustom.value ? (isCustomIdValid.value ? customId.value : '') : selectedVoice.value?.id || ''))

const selection = computed({
  get: () => (isCustom.value ? CUSTOM_OPTION : props.modelValue || ''),
  set: (value: string) => {
    isCustomChosen.value = value === CUSTOM_OPTION
    if (isCustomChosen.value) {
      customId.value = storedCustomId.value
      return
    }
    emit('update:modelValue', value)
  },
})

watch(storedCustomId, (id) => {
  if (id) customId.value = id
}, { immediate: true })

function onCustomInput(value: string): void {
  customId.value = value.trim()
  // Only a complete id is stored; until then the previous choice stays.
  if (isCustomIdValid.value) emit('update:modelValue', `${CUSTOM_PREFIX}${customId.value}`)
}

function voiceLabel(voice: TtsVoice): string {
  const details = [voice.gender, voice.age, voice.accent, voice.description].filter(Boolean).join(', ')
  return details ? `${voice.name} — ${details}` : voice.name
}

function stopPreview(): void {
  audioService.stop()
  isPreviewing.value = false
}

async function playSample(voiceId: string): Promise<void> {
  audioService.unlock()
  const name = props.npcName?.trim() || 'a stranger'
  await audioService.speak(`Well met, traveler. They call me ${name}. What brings you here?`, {
    voiceOverride: voiceId,
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
  previewHint.value = ''
  if (!supportsNpcVoices.value) {
    previewHint.value = 'Previews need ElevenLabs: choose it under Admin → Speech and add an ElevenLabs API key.'
    return
  }
  if (!previewVoiceId.value) {
    previewHint.value = isCustom.value ? 'Enter a complete voice id (20 characters) first.' : 'Pick a voice first.'
    return
  }
  isPreviewing.value = true
  try {
    await playSample(previewVoiceId.value)
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

    <div class="flex gap-2">
      <!-- color-scheme + option classes: native dropdown lists are light by default and unreadable here. -->
      <select
        v-model="selection"
        class="min-w-0 flex-1 bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-slate-300 focus:border-emerald-500 outline-none transition-all [color-scheme:dark]"
      >
        <option value="" class="bg-slate-900 text-slate-200">Automatic (cast from description)</option>
        <option v-if="isMissingVoice" :value="props.modelValue" class="bg-slate-900 text-slate-200">Removed voice (uses the narrator voice)</option>
        <option v-for="voice in voices" :key="voice.id" :value="voice.id" class="bg-slate-900 text-slate-200">{{ voiceLabel(voice) }}</option>
        <option :value="CUSTOM_OPTION" class="bg-slate-900 text-slate-200">Own voice ID…</option>
      </select>
      <button
        type="button"
        class="shrink-0 flex items-center gap-2 px-3 py-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-[10px] font-black uppercase tracking-widest text-emerald-400 hover:bg-emerald-500/10 transition-all"
        :class="{ 'opacity-40 grayscale': !supportsNpcVoices }"
        :title="isPreviewing ? 'Stop preview' : supportsNpcVoices ? 'Preview this voice' : 'Previews need ElevenLabs as speech provider'"
        @click="togglePreview"
      >
        <Square v-if="isPreviewing" class="w-3.5 h-3.5" />
        <Play v-else class="w-3.5 h-3.5" />
        <span>{{ isPreviewing ? 'Stop' : 'Preview' }}</span>
      </button>
    </div>

    <div v-if="isCustom" class="space-y-1">
      <input
        :value="customId"
        type="text"
        maxlength="20"
        placeholder="ElevenLabs voice ID, e.g. 21m00Tcm4TlvDq8ikWAM"
        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-slate-300 font-mono focus:border-emerald-500 outline-none transition-all"
        :class="{ 'border-red-500/60': customId && !isCustomIdValid }"
        @input="onCustomInput(($event.target as HTMLInputElement).value)"
      />
      <p class="text-[11px] leading-snug text-slate-500">
        Any voice of your ElevenLabs account (Voices → ⋯ → Copy voice ID). It is used even if it is not in the voice list.
      </p>
    </div>

    <p class="text-[11px] leading-snug text-slate-500">
      <template v-if="isMissingVoice">This voice is no longer in the voice list, so the narrator voice is used. Pick a new one.</template>
      <template v-else-if="selectedVoice?.good_for.length">Good for: {{ selectedVoice.good_for.join(', ') }}.</template>
      <template v-else-if="!selectedVoice && !isCustom">The game picks a fitting voice from the voice list that differs from the narrator and the other characters.</template>
    </p>
    <p v-if="!supportsNpcVoices" class="text-[11px] leading-snug text-amber-400/80">
      Character voices are spoken with ElevenLabs. With the current speech provider, all lines use the narrator
      voice; the choice made here takes effect once ElevenLabs is selected.
    </p>
    <p v-if="previewHint" class="text-[11px] text-amber-300">{{ previewHint }}</p>
    <p v-if="previewError" class="text-[11px] text-red-400">{{ previewError }}</p>
  </div>
</template>
