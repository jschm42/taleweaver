<script setup lang="ts">
import { computed } from 'vue'
import { AUDIO_DEFAULT_VOLUME, audioMuted, audioVolume, setAudioVolume } from '@/store/audioPreferences'
import SettingCard from './SettingCard.vue'
import SettingToggle from './SettingToggle.vue'

const audioOn = computed({
  get: (): boolean => !audioMuted.value,
  set: (value: boolean) => {
    audioMuted.value = !value
  },
})
const percent = computed((): number => Math.round(audioVolume.value * 100))

function onInput(event: Event): void {
  setAudioVolume(Number((event.target as HTMLInputElement).value) / 100)
}
</script>

<template>
  <SettingCard
    title="Background Audio"
    badge="Audio"
    badge-tone="cyan"
    description="Volume of the scene and script audio, relative to the voices (speech always plays at 100%)."
    :hint="`Applies immediately and is remembered in this browser. Default: ${Math.round(AUDIO_DEFAULT_VOLUME * 100)}%, about half as loud as the voices. Also used for the audio preview in the library.`"
  >
    <template #control>
      <SettingToggle v-model="audioOn" label="Background audio" />
    </template>
    <div class="mt-3 flex items-center gap-3" :class="{ 'opacity-40': !audioOn }">
      <input
        type="range"
        min="0"
        max="100"
        step="5"
        :value="percent"
        :disabled="!audioOn"
        aria-label="Audio volume"
        class="flex-1 accent-amber-500"
        @input="onInput"
      />
      <span class="w-10 text-right text-xs font-bold tabular-nums text-slate-300">{{ percent }}%</span>
      <button
        type="button"
        :disabled="!audioOn || percent === Math.round(AUDIO_DEFAULT_VOLUME * 100)"
        class="text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-white disabled:opacity-30"
        @click="setAudioVolume(AUDIO_DEFAULT_VOLUME)"
      >
        Reset
      </button>
    </div>
  </SettingCard>
</template>
