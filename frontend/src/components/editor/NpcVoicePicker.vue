<script setup lang="ts">
/**
 * NpcVoicePicker — Voice of an NPC or the protagonist: automatic, a voice from the voice list
 * (backend/core/elevenlabs_voices.json) or an own ElevenLabs voice id, stored as "custom:<id>".
 * Google TTS and OpenAI-compatible servers speak the voice the admin mapped to a list voice
 * (Admin → Character Voices); unmapped voices use the narrator voice.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Play, Square } from 'lucide-vue-next'
import { audioService } from '@/services/audioService'
import type { TtsVoice, TtsVoiceList } from '@/types'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import type { SelectOption } from '@/components/ui/UiSelect.vue'

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
const isElevenLabs = computed((): boolean => props.voiceList?.provider === 'elevenlabs')
const providerVoices = computed((): Record<string, string> => props.voiceList?.provider_voices ?? {})
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

const voiceOptions = computed((): SelectOption[] => [
  { value: '', label: 'Automatic (cast from description)' },
  ...(isMissingVoice.value ? [{ value: props.modelValue || '', label: 'Removed voice (uses the narrator voice)' }] : []),
  ...voices.value.map((voice) => ({ value: voice.id, label: voiceLabel(voice) })),
  { value: CUSTOM_OPTION, label: 'Own voice ID…' },
])

const voiceHint = computed((): string => {
  if (isMissingVoice.value) return 'This voice is no longer in the voice list, so the narrator voice is used. Pick a new one.'
  if (selectedVoice.value?.good_for.length) return `Good for: ${selectedVoice.value.good_for.join(', ')}.`
  if (!selectedVoice.value && !isCustom.value) return 'The game picks a fitting voice that differs from the narrator and the other characters.'
  return ''
})

function onCustomInput(value: string | number | null): void {
  customId.value = String(value ?? '').trim()
  // Only a complete id is stored; until then the previous choice stays.
  if (isCustomIdValid.value) emit('update:modelValue', `${CUSTOM_PREFIX}${customId.value}`)
}

function voiceLabel(voice: TtsVoice): string {
  const details = [voice.gender, voice.age, voice.accent, voice.description].filter(Boolean).join(', ')
  const label = details ? `${voice.name} — ${details}` : voice.name
  if (isElevenLabs.value || !supportsNpcVoices.value) return label
  const mapped = providerVoices.value[voice.id]
  return mapped ? `${label} (${mapped})` : `${label} (narrator voice)`
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
    previewHint.value = 'No character voices yet: choose ElevenLabs or map voices under Admin → Character Voices.'
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
    <UiField label="Voice" :hint="voiceHint">
      <div class="flex gap-2">
        <UiSelect
          :model-value="selection"
          :options="voiceOptions"
          class="min-w-0 flex-1"
          @update:model-value="(value) => (selection = String(value ?? ''))"
        />
        <UiButton
          :icon="isPreviewing ? Square : Play"
          :disabled="!supportsNpcVoices"
          :title="supportsNpcVoices ? undefined : 'No character voices with the current speech provider'"
          @click="togglePreview"
        >
          {{ isPreviewing ? 'Stop' : 'Preview' }}
        </UiButton>
      </div>
    </UiField>

    <UiField
      v-if="isCustom"
      label="ElevenLabs voice ID"
      hint="Any voice of your ElevenLabs account (Voices → ⋯ → Copy voice ID), even if it is not in the voice list."
      :error="customId && !isCustomIdValid ? 'A voice ID has 20 letters and digits.' : null"
    >
      <UiInput
        :model-value="customId"
        maxlength="20"
        mono
        placeholder="e.g. 21m00Tcm4TlvDq8ikWAM"
        @update:model-value="onCustomInput"
      />
    </UiField>

    <UiNotice v-if="!supportsNpcVoices" tone="warn">
      The current speech provider has no character voices yet, so all lines use the narrator voice. ElevenLabs speaks
      the list voices directly; for other providers an admin maps them under Admin → Character Voices.
    </UiNotice>
    <UiNotice v-else-if="isCustom && !isElevenLabs" tone="warn">
      Own voice IDs are ElevenLabs voices; with the current speech provider this character uses the narrator voice.
    </UiNotice>
    <UiNotice v-if="previewHint" tone="warn">{{ previewHint }}</UiNotice>
    <UiNotice v-if="previewError" tone="danger">{{ previewError }}</UiNotice>
  </div>
</template>
