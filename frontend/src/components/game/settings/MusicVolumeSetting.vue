<script setup lang="ts">
import { computed } from 'vue'
import { MUSIC_DEFAULT_VOLUME, musicMuted, musicVolume, setMusicVolume } from '@/store/musicPreferences'
import SettingCard from './SettingCard.vue'
import SettingToggle from './SettingToggle.vue'

const musicOn = computed({
  get: (): boolean => !musicMuted.value,
  set: (value: boolean) => {
    musicMuted.value = !value
  },
})
const percent = computed((): number => Math.round(musicVolume.value * 100))

function onInput(event: Event): void {
  setMusicVolume(Number((event.target as HTMLInputElement).value) / 100)
}
</script>

<template>
  <SettingCard
    title="Background Music"
    badge="Audio"
    badge-tone="cyan"
    description="Volume of the scene and script music, relative to the voices (speech always plays at 100%)."
    :hint="`Applies immediately and is remembered in this browser. Default: ${Math.round(MUSIC_DEFAULT_VOLUME * 100)}%, about half as loud as the voices. Also used for the music preview in the library.`"
  >
    <template #control>
      <SettingToggle v-model="musicOn" label="Background music" />
    </template>
    <div class="mt-3 flex items-center gap-3" :class="{ 'opacity-40': !musicOn }">
      <input
        type="range"
        min="0"
        max="100"
        step="5"
        :value="percent"
        :disabled="!musicOn"
        aria-label="Music volume"
        class="flex-1 accent-amber-500"
        @input="onInput"
      />
      <span class="w-10 text-right text-xs font-bold tabular-nums text-slate-300">{{ percent }}%</span>
      <button
        type="button"
        :disabled="!musicOn || percent === Math.round(MUSIC_DEFAULT_VOLUME * 100)"
        class="text-[10px] font-bold uppercase tracking-wider text-slate-400 hover:text-white disabled:opacity-30"
        @click="setMusicVolume(MUSIC_DEFAULT_VOLUME)"
      >
        Reset
      </button>
    </div>
  </SettingCard>
</template>
