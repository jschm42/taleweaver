<script setup lang="ts">
import { VolumeX } from 'lucide-vue-next'
import type { AutoSpeakSettings } from '@/types/tts'
import AutoSpeakChannelTable from './AutoSpeakChannelTable.vue'
import SettingCard from './SettingCard.vue'
import SettingToggle from './SettingToggle.vue'
import AudioVolumeSetting from './AudioVolumeSetting.vue'

const autoSpeech = defineModel<boolean>('autoSpeech', { required: true })
const autoSpeakSettings = defineModel<AutoSpeakSettings>('autoSpeakSettings', { required: true })

const props = defineProps<{
  ttsAvailable: boolean
}>()
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

    <AudioVolumeSetting />
  </div>
</template>
