<script setup lang="ts">
/** Profile preference: how the in-game clock shows the time in adventures with a day clock. */
import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import { authState, refreshUser, type ClockFormat } from '@/store/auth'

const emit = defineEmits<{ (e: 'notify', message: string, type: 'success' | 'error'): void }>()

const OPTIONS: { value: ClockFormat; label: string }[] = [
  { value: 'adventure', label: 'As the adventure sets it' },
  { value: '24h', label: '24-hour (14:30)' },
  { value: '12h', label: '12-hour (02:30 PM)' },
]

const selected = ref<ClockFormat>(authState.user?.clock_format || 'adventure')
const isSaving = ref(false)

watch(() => authState.user?.clock_format, (value) => {
  selected.value = value || 'adventure'
})

async function save(): Promise<void> {
  isSaving.value = true
  try {
    await api.updateMyPreferences({ clock_format: selected.value })
    await refreshUser()
    emit('notify', 'Clock format saved.', 'success')
  } catch (err: unknown) {
    selected.value = authState.user?.clock_format || 'adventure'
    emit('notify', err instanceof Error && err.message ? err.message : 'Failed to save clock format.', 'error')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4 rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5 sm:flex-row sm:items-center">
    <div class="flex min-w-0 flex-1 items-start gap-3">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-400/10 text-amber-300">
        <i class="ra ra-hourglass text-lg"></i>
      </div>
      <div class="min-w-0">
        <h4 class="font-display text-lg text-white">In-game clock</h4>
        <p class="text-xs text-slate-400">
          Time format for adventures with a day clock. Adventures that count custom units are not affected.
        </p>
      </div>
    </div>
    <div class="flex items-center gap-2 sm:w-56">
      <label for="profile-clock-format" class="sr-only">Clock format</label>
      <select
        id="profile-clock-format"
        v-model="selected"
        :disabled="isSaving"
        class="w-full cursor-pointer rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-amber-400/60"
        @change="save"
      >
        <option v-for="option in OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
      </select>
      <i v-if="isSaving" class="ra ra-cycle animate-spin text-amber-300"></i>
    </div>
  </div>
</template>
