<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import { authState, refreshUser } from '@/store/auth'
import ChangeCredentialsModal from '@/components/portal/ChangeCredentialsModal.vue'
import AutoSpeakPreferencesCard from './AutoSpeakPreferencesCard.vue'
import PersonalApiKeysCard from './PersonalApiKeysCard.vue'
import RecoveryCodesCard from './RecoveryCodesCard.vue'

const emit = defineEmits<{ (e: 'notify', message: string, type: 'success' | 'error'): void }>()

const LANGUAGES = [
  { code: '', name: 'Default (English)' },
  { code: 'German', name: 'Deutsch' },
  { code: 'English', name: 'English' },
  { code: 'French', name: 'Français' },
  { code: 'Spanish', name: 'Español' },
  { code: 'Italian', name: 'Italiano' },
  { code: 'Japanese', name: '日本語' },
  { code: 'Chinese', name: '中文' },
  { code: 'Russian', name: 'Русский' },
  { code: 'Portuguese', name: 'Português' },
]

const selectedLanguage = ref(authState.user?.default_language || '')
const isSavingLanguage = ref(false)
const isCredentialsOpen = ref(false)

watch(() => authState.user?.default_language, (value) => {
  selectedLanguage.value = value || ''
})

async function saveLanguage(): Promise<void> {
  isSavingLanguage.value = true
  try {
    await api.updateMyPreferences({ default_language: selectedLanguage.value || null })
    await refreshUser()
    emit('notify', 'Default language saved.', 'success')
  } catch (err: unknown) {
    selectedLanguage.value = authState.user?.default_language || ''
    emit('notify', err instanceof Error && err.message ? err.message : 'Failed to save language preference.', 'error')
  } finally {
    isSavingLanguage.value = false
  }
}
</script>

<template>
  <div class="space-y-8">
    <!-- Preferences -->
    <section class="space-y-4" aria-labelledby="profile-preferences-heading">
      <h3 id="profile-preferences-heading" class="px-1 text-[11px] font-black uppercase tracking-widest text-slate-500">Preferences</h3>

      <div class="flex flex-col gap-4 rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5 sm:flex-row sm:items-center">
        <div class="flex min-w-0 flex-1 items-start gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-400/10 text-cyan-300">
            <i class="ra ra-fish text-lg"></i>
          </div>
          <div class="min-w-0">
            <h4 class="font-display text-lg text-white">Babel Fish</h4>
            <p class="text-xs text-slate-400">Default language for narration and translation in new adventures.</p>
          </div>
        </div>
        <div class="flex items-center gap-2 sm:w-56">
          <label for="profile-language" class="sr-only">Default language</label>
          <select
            id="profile-language"
            v-model="selectedLanguage"
            :disabled="isSavingLanguage"
            class="w-full cursor-pointer rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400/60"
            @change="saveLanguage"
          >
            <option v-for="lang in LANGUAGES" :key="lang.code" :value="lang.code">{{ lang.name }}</option>
          </select>
          <i v-if="isSavingLanguage" class="ra ra-cycle animate-spin text-cyan-300"></i>
        </div>
      </div>

      <AutoSpeakPreferencesCard @notify="(message, type) => emit('notify', message, type)" />

      <PersonalApiKeysCard @notify="(message, type) => emit('notify', message, type)" />
    </section>

    <!-- Security -->
    <section class="space-y-4" aria-labelledby="profile-security-heading">
      <h3 id="profile-security-heading" class="px-1 text-[11px] font-black uppercase tracking-widest text-slate-500">Security</h3>

      <div class="flex flex-col gap-4 rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5 sm:flex-row sm:items-center">
        <div class="flex min-w-0 flex-1 items-start gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-aether-primary/10 text-aether-primary">
            <i class="ra ra-shield text-lg"></i>
          </div>
          <div class="min-w-0">
            <h4 class="font-display text-lg text-white">Sign-in credentials</h4>
            <p class="text-xs text-slate-400">
              Signed in as <span class="text-slate-200">{{ authState.user?.username }}</span>.
              Changing your password signs out all other devices.
            </p>
          </div>
        </div>
        <button
          type="button"
          class="shrink-0 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-200 transition-all hover:border-aether-primary/40 hover:text-aether-primary"
          @click="isCredentialsOpen = true"
        >
          Change username or password
        </button>
      </div>

      <RecoveryCodesCard @notify="(message, type) => emit('notify', message, type)" />
    </section>

    <ChangeCredentialsModal :is-open="isCredentialsOpen" @close="isCredentialsOpen = false" />
  </div>
</template>
