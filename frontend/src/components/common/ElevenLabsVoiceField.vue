<script setup lang="ts">
/**
 * ElevenLabsVoiceField — Narrator voice for ElevenLabs: pick from the voice list
 * (backend/core/elevenlabs_voices.json) or enter any other voice id of the account.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import type { TtsVoice } from '@/types'

const CUSTOM = '__custom__'

const props = defineProps<{
  modelValue: string
  inputClass: string
  inputId?: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const voices = ref<TtsVoice[]>([])
const isCustom = ref(false)

const isListed = computed(() => voices.value.some((voice) => voice.id === props.modelValue))

const selection = computed({
  get: () => (isCustom.value || (props.modelValue && !isListed.value) ? CUSTOM : props.modelValue),
  set: (value: string) => {
    isCustom.value = value === CUSTOM
    if (!isCustom.value) emit('update:modelValue', value)
  },
})

function voiceLabel(voice: TtsVoice): string {
  const details = [voice.gender, voice.accent, voice.description].filter(Boolean).join(', ')
  return details ? `${voice.name} — ${details}` : voice.name
}

onMounted(async () => {
  try {
    voices.value = (await api.getTtsVoices('elevenlabs')).voices
  } catch (error) {
    console.warn('Could not load the voice list', error)
  }
})

watch(isListed, (listed) => {
  if (listed) isCustom.value = false
})
</script>

<template>
  <div class="space-y-2">
    <select :id="inputId" v-model="selection" :class="[inputClass, '[color-scheme:dark]']">
      <option v-if="!modelValue && !isCustom" value="" disabled class="bg-slate-900 text-slate-200">Choose a narrator voice…</option>
      <option v-for="voice in voices" :key="voice.id" :value="voice.id" class="bg-slate-900 text-slate-200">{{ voiceLabel(voice) }}</option>
      <option :value="CUSTOM" class="bg-slate-900 text-slate-200">Other voice ID…</option>
    </select>
    <input
      v-if="selection === CUSTOM"
      :value="modelValue"
      type="text"
      placeholder="e.g. 21m00Tcm4TlvDq8ikWAM"
      :class="[inputClass, 'font-mono']"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value.trim())"
    />
  </div>
</template>
