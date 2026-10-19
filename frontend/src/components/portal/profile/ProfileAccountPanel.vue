<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import { authState, refreshUser } from '@/store/auth'
import ChangeCredentialsModal from '@/components/portal/ChangeCredentialsModal.vue'
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

async function saveLanguage() {
  isSavingLanguage.value = true
  try {
    await api.updateMyPreferences({ default_language: selectedLanguage.value || null })
    await refreshUser()
    emit('notify', 'Default language saved.', 'success')
  } catch (err: any) {
    selectedLanguage.value = authState.user?.default_language || ''
    emit('notify', err?.message || 'Failed to save language preference.', 'error')
  } finally {
    isSavingLanguage.value = false
  }
}
</script>

<template>
  <div class="grid gap-5 lg:grid-cols-2">
    <!-- Language -->
    <section class="rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5 sm:p-6">
      <div class="flex items-start gap-3">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cyan-400/10 text-cyan-300">
          <i class="ra ra-fish text-lg"></i>
        </div>
        <div class="min-w-0 flex-1">
          <h3 class="font-display text-lg text-white">Bable Fish</h3>
          <p class="text-xs text-slate-400">Default language for narration and translation in new adventures.</p>
          <div class="mt-4 flex items-center gap-2">
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
      </div>
    </section>

    <!-- Credentials -->
    <section class="rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5 sm:p-6">
      <div class="flex items-start gap-3">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-aether-primary/10 text-aether-primary">
          <i class="ra ra-shield text-lg"></i>
        </div>
        <div class="min-w-0 flex-1">
          <h3 class="font-display text-lg text-white">Sign-in credentials</h3>
          <p class="text-xs text-slate-400">
            Signed in as <span class="text-slate-200">{{ authState.user?.username }}</span>.
            Changing your password signs out all other devices.
          </p>
          <button
            type="button"
            class="mt-4 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-200 transition-all hover:border-aether-primary/40 hover:text-aether-primary"
            @click="isCredentialsOpen = true"
          >
            Change username or password
          </button>
        </div>
      </div>
    </section>

    <RecoveryCodesCard class="lg:col-span-2" @notify="(message, type) => emit('notify', message, type)" />

    <ChangeCredentialsModal :is-open="isCredentialsOpen" @close="isCredentialsOpen = false" />
  </div>
</template>
