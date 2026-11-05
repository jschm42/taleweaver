<script setup lang="ts">
import { AUTO_SPEAK_CHANNELS, type AutoSpeakChannel, type AutoSpeakSettings } from '@/types/tts'

/** Compact list of the Auto-Speak voice channels, one ON/OFF button per row. */
const settings = defineModel<AutoSpeakSettings>({ required: true })

const props = defineProps<{
  disabled?: boolean
}>()

function toggle(key: AutoSpeakChannel) {
  settings.value = { ...settings.value, [key]: !settings.value[key] }
}
</script>

<template>
  <ul
    class="divide-y divide-white/5 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/40"
    :class="{ 'opacity-50': props.disabled }"
  >
    <li v-for="channel in AUTO_SPEAK_CHANNELS" :key="channel.key" class="flex items-center gap-3 px-3 py-2.5">
      <i :class="['ra', channel.icon, 'w-5 shrink-0 text-center text-base text-amber-400/80']" aria-hidden="true"></i>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold leading-tight text-slate-100">{{ channel.label }}</p>
        <p class="truncate text-[11px] leading-tight text-slate-400">{{ channel.description }}</p>
      </div>
      <button
        type="button"
        role="switch"
        :aria-checked="settings[channel.key]"
        :aria-label="`Auto-speak ${channel.label}`"
        :disabled="props.disabled"
        class="w-14 shrink-0 rounded-lg border py-1 text-[10px] font-black uppercase tracking-widest transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 disabled:cursor-not-allowed cursor-pointer"
        :class="
          settings[channel.key]
            ? 'border-amber-400 bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
            : 'border-slate-700 bg-slate-800 text-slate-400 hover:text-slate-200'
        "
        @click="toggle(channel.key)"
      >
        {{ settings[channel.key] ? 'On' : 'Off' }}
      </button>
    </li>
  </ul>
</template>
