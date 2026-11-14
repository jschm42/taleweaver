<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { authState, refreshUser } from '@/store/auth'
import { finishOnboarding, loadOnboarding, onboardingState, resetOnboarding } from '@/store/onboarding'
import { normalizeTtsPreferences } from '@/types/tts'

const STEPS = [
  { id: 'welcome', label: 'Welcome' },
  { id: 'language', label: 'Language' },
  { id: 'voice', label: 'Voice' },
] as const

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

const stepIndex = ref(0)
const selectedLanguage = ref('')
const autoSpeak = ref(true)
const isSaving = ref(false)
const saveError = ref('')

const currentStep = computed(() => STEPS[stepIndex.value].id)
const isOpen = computed((): boolean => onboardingState.isOpen && authState.user?.role !== 'admin')

function hydrate(): void {
  stepIndex.value = 0
  saveError.value = ''
  selectedLanguage.value = authState.user?.default_language || ''
  autoSpeak.value = normalizeTtsPreferences(authState.user?.tts_preferences).enabled
}

async function saveLanguage(): Promise<void> {
  isSaving.value = true
  saveError.value = ''
  try {
    await api.updateMyPreferences({ default_language: selectedLanguage.value || null })
    await refreshUser()
    stepIndex.value += 1
  } catch (error) {
    console.error('[Onboarding] Saving the language failed:', error)
    saveError.value = 'The language could not be saved. Please try again.'
  } finally {
    isSaving.value = false
  }
}

async function finish(): Promise<void> {
  isSaving.value = true
  saveError.value = ''
  try {
    const preferences = normalizeTtsPreferences(authState.user?.tts_preferences)
    await api.updateMyPreferences({ tts_preferences: { ...preferences, enabled: autoSpeak.value } })
    await refreshUser()
    await finishOnboarding('completed')
  } catch (error) {
    console.error('[Onboarding] Saving the voice preference failed:', error)
    saveError.value = 'The voice setting could not be saved. Please try again.'
  } finally {
    isSaving.value = false
  }
}

async function skip(): Promise<void> {
  await finishOnboarding('skipped')
}

function back(): void {
  saveError.value = ''
  stepIndex.value -= 1
}

watch(
  () => authState.user?.id,
  (userId) => {
    resetOnboarding()
    if (userId && authState.user?.role !== 'admin') {
      loadOnboarding()
    }
  },
  { immediate: true },
)

watch(isOpen, (open) => {
  if (open) {
    hydrate()
  }
})
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="isOpen"
      class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="user-onboarding-title"
    >
      <div class="relative w-full max-w-lg max-h-[92vh] flex flex-col bg-[#0d1117] border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-aether-primary to-transparent"></div>

        <!-- Header + step indicator -->
        <div class="px-8 pt-7 pb-5 border-b border-white/5">
          <div class="flex items-center justify-between mb-5">
            <div>
              <h2 id="user-onboarding-title" class="text-xl font-black text-white uppercase tracking-tighter leading-none mb-1">
                Welcome to TaleWeaver
              </h2>
              <p class="text-aether-primary/60 text-[10px] font-bold uppercase tracking-[0.2em]">
                Step {{ stepIndex + 1 }} of {{ STEPS.length }}
              </p>
            </div>
            <button
              type="button"
              class="w-10 h-10 rounded-full flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/5 transition-all"
              title="Close (skip for now)"
              aria-label="Close (skip for now)"
              @click="skip"
            >
              <X class="w-6 h-6" />
            </button>
          </div>
          <ol class="flex items-center gap-2">
            <li
              v-for="(step, index) in STEPS"
              :key="step.id"
              class="w-2.5 h-2.5 rounded-full transition-colors"
              :class="index <= stepIndex ? 'bg-aether-primary' : 'bg-white/10'"
              :title="step.label"
            ></li>
          </ol>
        </div>

        <!-- Page -->
        <div class="flex-1 overflow-y-auto px-8 py-6 space-y-4">
          <template v-if="currentStep === 'welcome'">
            <h3 class="text-lg font-bold text-white">Hello, {{ authState.user?.username }}!</h3>
            <p class="text-sm text-slate-400 leading-relaxed">
              TaleWeaver lets you create your own adventures and play the ones already in the library.
              This short assistant helps you with your first personal settings. You can change them later in your profile.
            </p>
          </template>

          <template v-else-if="currentStep === 'language'">
            <h3 class="text-lg font-bold text-white">Story language</h3>
            <p class="text-sm text-slate-400 leading-relaxed">
              The language the Game Master uses to tell your stories.
            </p>
            <select
              v-model="selectedLanguage"
              class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:border-aether-primary/50"
            >
              <option v-for="lang in LANGUAGES" :key="lang.code" :value="lang.code">{{ lang.name }}</option>
            </select>
          </template>

          <template v-else>
            <h3 class="text-lg font-bold text-white">Voice</h3>
            <p class="text-sm text-slate-400 leading-relaxed">
              New adventures can read the narration aloud as it appears.
            </p>
            <label class="flex items-center justify-between gap-4 p-4 rounded-2xl border border-white/10 bg-black/30 cursor-pointer select-none">
              <span class="text-sm font-bold text-white">Read narration aloud automatically</span>
              <input v-model="autoSpeak" type="checkbox" class="w-5 h-5 accent-emerald-400 cursor-pointer" />
            </label>
          </template>

          <p v-if="saveError" class="text-xs font-bold text-red-400">{{ saveError }}</p>
        </div>

        <!-- Footer -->
        <div class="px-8 py-5 border-t border-white/5 flex items-center justify-between gap-4">
          <button
            type="button"
            class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 hover:text-white transition-all"
            :disabled="isSaving"
            @click="skip"
          >
            Skip for now
          </button>
          <div class="flex items-center gap-2">
            <button
              v-if="stepIndex > 0"
              type="button"
              class="px-4 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 hover:text-white transition-all"
              :disabled="isSaving"
              @click="back"
            >
              Back
            </button>
            <button
              v-if="currentStep === 'welcome'"
              type="button"
              class="px-6 py-2.5 rounded-xl bg-aether-primary text-slate-950 text-[10px] font-black uppercase tracking-[0.2em] hover:brightness-110 transition-all"
              @click="stepIndex += 1"
            >
              Let's go
            </button>
            <button
              v-else-if="currentStep === 'language'"
              type="button"
              class="px-6 py-2.5 rounded-xl bg-aether-primary text-slate-950 text-[10px] font-black uppercase tracking-[0.2em] hover:brightness-110 transition-all disabled:opacity-50"
              :disabled="isSaving"
              @click="saveLanguage"
            >
              {{ isSaving ? 'Saving…' : 'Save & continue' }}
            </button>
            <button
              v-else
              type="button"
              class="px-6 py-2.5 rounded-xl bg-aether-primary text-slate-950 text-[10px] font-black uppercase tracking-[0.2em] hover:brightness-110 transition-all disabled:opacity-50"
              :disabled="isSaving"
              @click="finish"
            >
              {{ isSaving ? 'Saving…' : 'Finish' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>
