<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import { authState, refreshUser } from '@/store/auth'
import { normalizeTtsPreferences, type AutoSpeakSettings, type TtsPreferences } from '@/types/tts'
import AutoSpeakChannelTable from '@/components/game/settings/AutoSpeakChannelTable.vue'
import SettingToggle from '@/components/game/settings/SettingToggle.vue'

const emit = defineEmits<{ (e: 'notify', message: string, type: 'success' | 'error'): void }>()

const preferences = ref<TtsPreferences>(normalizeTtsPreferences(authState.user?.tts_preferences))
const isSaving = ref(false)

watch(() => authState.user?.tts_preferences, (value) => {
  preferences.value = normalizeTtsPreferences(value)
})

const enabled = computed({
  get: () => preferences.value.enabled,
  set: (value: boolean) => save({ ...preferences.value, enabled: value }),
})

const channels = computed<AutoSpeakSettings>({
  get: () => preferences.value,
  set: (value) => save({ ...value, enabled: preferences.value.enabled }),
})

async function save(next: TtsPreferences) {
  const previous = preferences.value
  preferences.value = next
  isSaving.value = true
  try {
    await api.updateMyPreferences({ tts_preferences: next })
    await refreshUser()
    emit('notify', 'Auto-Speak preferences saved.', 'success')
  } catch (err: any) {
    preferences.value = previous
    emit('notify', err?.message || 'Failed to save Auto-Speak preferences.', 'error')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <section class="rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5 sm:p-6">
    <div class="flex items-start gap-3">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-400/10 text-amber-300">
        <i class="ra ra-speech-bubbles text-lg"></i>
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h3 class="font-display text-lg text-white">Auto-Speak Preferences</h3>
            <p class="text-xs text-slate-400">
              Defaults for new adventures. Each session keeps its own copy, which you can change in its settings.
            </p>
          </div>
          <SettingToggle v-model="enabled" label="Auto-Speak" :disabled="isSaving" />
        </div>
        <AutoSpeakChannelTable v-model="channels" class="mt-4" :disabled="isSaving || !preferences.enabled" />
      </div>
    </div>
  </section>
</template>
