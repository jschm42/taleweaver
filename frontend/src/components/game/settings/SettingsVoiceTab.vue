<script setup lang="ts">
import { computed } from 'vue'
import { VolumeX } from 'lucide-vue-next'
import { musicService } from '@/services/musicService'
import type { AutoSpeakSettings } from '@/types/tts'
import AutoSpeakChannelTable from './AutoSpeakChannelTable.vue'
import SettingCard from './SettingCard.vue'
import SettingToggle from './SettingToggle.vue'

const autoSpeech = defineModel<boolean>('autoSpeech', { required: true })
const autoSpeakSettings = defineModel<AutoSpeakSettings>('autoSpeakSettings', { required: true })

const props = defineProps<{
  ttsAvailable: boolean
}>()

const musicEnabled = computed<boolean>({
  get: () => !musicService.isMuted.value,
  set: (enabled) => musicService.setMuted(!enabled),
})
const musicVolumePercent = computed<number>(() => Math.round(musicService.volume.value * 100))

function onMusicVolumeInput(event: Event): void {
  musicService.setVolume(Number((event.target as HTMLInputElement).value) / 100)
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <p class="text-xs leading-relaxed text-slate-400">
      Let the Game Master and the characters speak. New story passages are converted to speech as they arrive,
      using the voices configured for the adventure.
    </p>

    <div
      v-if="!props.ttsAvailable"
      class="flex items-start gap-3 rounded-2xl border border-slate-700/60 bg-slate-900/60 p-4 text-xs leading-relaxed text-slate-400"
    >
      <VolumeX class="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
      <span>
        Speech output is not available. An administrator has to enable and configure a text-to-speech provider in
        the system settings first.
      </span>
    </div>

    <template v-else>
      <SettingCard
        title="Auto-Speak"
        badge="Audio"
        badge-tone="blue"
        description="Master switch: automatically read new story passages aloud."
        hint="Only passages that arrive after you enable this are spoken, so your existing log is not replayed. Some browsers block audio until you have interacted with the page once. Speech pauses automatically during combat."
      >
        <template #control>
          <SettingToggle v-model="autoSpeech" label="Auto-Speak" />
        </template>
      </SettingCard>

      <div v-if="autoSpeech" class="flex flex-col gap-2">
        <p class="px-1 text-[10px] font-black uppercase tracking-widest text-slate-500">Read aloud</p>
        <AutoSpeakChannelTable v-model="autoSpeakSettings" />
      </div>
    </template>

    <SettingCard
      title="Background Music"
      badge="Audio"
      badge-tone="cyan"
      description="Play the music the adventure assigns to scenes, and the sounds its scripts trigger."
      hint="Mute and volume are stored in this browser and apply to every adventure. Some browsers block audio until you have interacted with the page once."
    >
      <template #control>
        <SettingToggle v-model="musicEnabled" label="Background Music" />
      </template>

      <div class="mt-4 flex items-center gap-3" :class="{ 'opacity-50': !musicEnabled }">
        <input
          type="range"
          min="0"
          max="100"
          :value="musicVolumePercent"
          :disabled="!musicEnabled"
          aria-label="Music volume"
          class="h-2 w-full cursor-pointer rounded-lg bg-slate-800 accent-amber-500 disabled:cursor-not-allowed"
          @input="onMusicVolumeInput"
        />
        <span class="w-10 text-right font-mono text-xs font-bold text-amber-400">{{ musicVolumePercent }}%</span>
      </div>
    </SettingCard>
  </div>
</template>
