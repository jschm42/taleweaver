<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/composables/useApi'
import { authState, refreshUser } from '@/store/auth'

const emit = defineEmits<{ (e: 'notify', message: string, type: 'success' | 'error'): void }>()

const remaining = computed(() => authState.user?.recovery_codes_remaining ?? 0)
const isConfirming = ref(false)
const currentPassword = ref('')
const isGenerating = ref(false)
const error = ref('')
const codes = ref<string[]>([])
const copied = ref(false)

function startGenerate() {
  isConfirming.value = true
  currentPassword.value = ''
  error.value = ''
}

async function generate() {
  if (!currentPassword.value || isGenerating.value) return
  isGenerating.value = true
  error.value = ''
  try {
    codes.value = (await api.regenerateMyRecoveryCodes(currentPassword.value)).codes
    isConfirming.value = false
    copied.value = false
    await refreshUser()
  } catch (err: any) {
    error.value = err?.message || 'Failed to create recovery codes.'
  } finally {
    isGenerating.value = false
    currentPassword.value = ''
  }
}

async function copyCodes() {
  try {
    await navigator.clipboard.writeText(codes.value.join('\n'))
    copied.value = true
  } catch {
    emit('notify', 'Copy failed. Please write the codes down manually.', 'error')
  }
}

function downloadCodes() {
  const username = authState.user?.username || 'account'
  const content = [
    `TaleWeaver recovery codes for ${username}`,
    `Created ${new Date().toISOString()}`,
    'Each code can be used once to reset your password.',
    '',
    ...codes.value,
  ].join('\n')
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `taleweaver-recovery-codes-${username}.txt`
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

function dismissCodes() {
  codes.value = []
  emit('notify', 'Recovery codes stored. Keep them somewhere safe.', 'success')
}
</script>

<template>
  <section class="rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5 sm:p-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div class="flex items-start gap-3">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-400/10 text-amber-300">
          <i class="ra ra-key text-lg"></i>
        </div>
        <div>
          <h3 class="font-display text-lg text-white">Recovery codes</h3>
          <p class="max-w-md text-xs leading-relaxed text-slate-400">
            One-time codes that let you reset a forgotten password from the sign-in page.
            Creating new codes invalidates the old ones.
          </p>
        </div>
      </div>
      <span
        class="rounded-full border px-2.5 py-0.5 text-[11px] font-black uppercase tracking-widest"
        :class="remaining ? 'border-aether-primary/30 bg-aether-primary/10 text-aether-primary' : 'border-amber-400/30 bg-amber-400/10 text-amber-300'"
      >
        {{ remaining ? `${remaining} unused` : 'Not set up' }}
      </span>
    </div>

    <!-- Freshly generated codes (shown once) -->
    <div v-if="codes.length" class="mt-5 space-y-4 rounded-xl border border-amber-400/30 bg-amber-400/5 p-4">
      <p class="text-xs font-bold text-amber-200">Save these codes now. They will not be shown again.</p>
      <ol class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <li v-for="code in codes" :key="code" class="rounded-lg bg-black/40 px-3 py-2 text-center font-mono text-sm tracking-[0.2em] text-white">
          {{ code }}
        </li>
      </ol>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold text-slate-200 hover:text-white" @click="copyCodes">
          {{ copied ? 'Copied' : 'Copy all' }}
        </button>
        <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold text-slate-200 hover:text-white" @click="downloadCodes">
          Download .txt
        </button>
        <button type="button" class="ml-auto rounded-lg bg-aether-primary px-3 py-1.5 text-xs font-black text-[#081425] hover:bg-emerald-300" @click="dismissCodes">
          I saved them
        </button>
      </div>
    </div>

    <!-- Password confirmation -->
    <form v-else-if="isConfirming" class="mt-5 space-y-3" @submit.prevent="generate">
      <label class="block space-y-1.5">
        <span class="text-[11px] font-black uppercase tracking-widest text-slate-500">Confirm with your current password</span>
        <input
          v-model="currentPassword"
          type="password"
          autocomplete="current-password"
          required
          class="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-2.5 text-sm text-white outline-none focus:border-aether-primary/50"
        />
      </label>
      <p v-if="error" class="text-xs text-red-400">{{ error }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="px-3 py-1.5 text-xs font-bold text-slate-400 hover:text-white" @click="isConfirming = false">Cancel</button>
        <button type="submit" :disabled="!currentPassword || isGenerating" class="rounded-lg bg-aether-primary px-4 py-1.5 text-xs font-black text-[#081425] hover:bg-emerald-300 disabled:opacity-50">
          {{ isGenerating ? 'Creating...' : 'Create codes' }}
        </button>
      </div>
    </form>

    <button
      v-else
      type="button"
      class="mt-5 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-200 transition-all hover:border-amber-300/40 hover:text-amber-200"
      @click="startGenerate"
    >
      {{ remaining ? 'Create new codes' : 'Set up recovery codes' }}
    </button>
  </section>
</template>
