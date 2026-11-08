<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type MyApiKeysResponse, type PersonalKeyProvider } from '@/composables/useApi'
import { refreshConfig } from '@/store/config'

/** The player's own provider keys; shown only when the server lets players bring a key. */
const emit = defineEmits<{ (e: 'notify', message: string, type: 'success' | 'error'): void }>()

const state = ref<MyApiKeysResponse | null>(null)
const drafts = ref<Record<string, string>>({})
const busyProvider = ref<string | null>(null)

const providers = computed<PersonalKeyProvider[]>(
  () => (state.value?.providers || []).filter(p => p.can_store_key),
)

const STATUS: Record<string, { label: string, tone: string }> = {
  personal: { label: 'Own key', tone: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' },
  server: { label: 'Server pays', tone: 'border-sky-400/30 bg-sky-400/10 text-sky-300' },
  missing: { label: 'Key required', tone: 'border-amber-400/40 bg-amber-400/10 text-amber-200' },
  disabled: { label: 'Disabled', tone: 'border-white/10 bg-white/5 text-slate-400' },
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

async function load(): Promise<void> {
  try {
    state.value = await api.getMyApiKeys()
  } catch {
    state.value = null
  }
}

async function save(provider: PersonalKeyProvider): Promise<void> {
  const key = (drafts.value[provider.id] || '').trim()
  if (!key) return
  busyProvider.value = provider.id
  try {
    state.value = await api.storeMyApiKey(provider.id, key)
    drafts.value[provider.id] = ''
    void refreshConfig()
    const note = state.value.verified ? 'verified and saved' : 'saved (could not be verified automatically)'
    emit('notify', `${provider.name} key ${note}.`, 'success')
  } catch (err: unknown) {
    emit('notify', errorMessage(err, `Failed to save the ${provider.name} key.`), 'error')
  } finally {
    busyProvider.value = null
  }
}

async function remove(provider: PersonalKeyProvider): Promise<void> {
  if (!confirm(`Remove your ${provider.name} key?`)) return
  busyProvider.value = provider.id
  try {
    state.value = await api.deleteMyApiKey(provider.id)
    void refreshConfig()
    emit('notify', `${provider.name} key removed.`, 'success')
  } catch (err: unknown) {
    emit('notify', errorMessage(err, `Failed to remove the ${provider.name} key.`), 'error')
  } finally {
    busyProvider.value = null
  }
}

onMounted(() => { void load() })
</script>

<template>
  <section v-if="providers.length" class="rounded-2xl border border-white/10 bg-[#0b1322]/80 p-5">
    <div class="flex items-start gap-3">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-400/10 text-amber-300">
        <i class="ra ra-key text-lg"></i>
      </div>
      <div class="min-w-0">
        <h4 class="font-display text-lg text-white">API keys</h4>
        <p class="text-xs text-slate-400">
          Use your own provider keys; usage is then billed to your account at the provider.
          Keys are stored encrypted and never shown again.
        </p>
      </div>
    </div>

    <ul class="mt-4 divide-y divide-white/5">
      <li v-for="provider in providers" :key="provider.id" class="flex flex-col gap-2 py-3 sm:flex-row sm:items-center">
        <div class="flex min-w-0 items-center gap-2 sm:w-52">
          <span class="truncate text-sm font-bold text-white">{{ provider.name }}</span>
          <span class="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-widest" :class="STATUS[provider.source]?.tone">
            {{ STATUS[provider.source]?.label || provider.source }}
          </span>
        </div>
        <form class="flex min-w-0 flex-1 items-center gap-2" @submit.prevent="save(provider)">
          <label class="sr-only" :for="`personal-key-${provider.id}`">{{ provider.name }} API key</label>
          <input
            :id="`personal-key-${provider.id}`"
            v-model="drafts[provider.id]"
            type="password"
            autocomplete="off"
            spellcheck="false"
            maxlength="512"
            :placeholder="provider.has_personal_key ? 'Replace stored key...' : 'Paste your key...'"
            class="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/40 px-3 py-2 font-mono text-xs text-white outline-none focus:border-amber-400/50"
          />
          <button
            type="submit"
            :disabled="busyProvider === provider.id || !(drafts[provider.id] || '').trim()"
            class="shrink-0 rounded-lg bg-amber-400/90 px-3 py-2 text-[11px] font-black uppercase tracking-widest text-[#081425] hover:bg-amber-300 disabled:opacity-40"
          >
            <i v-if="busyProvider === provider.id" class="ra ra-cycle animate-spin"></i>
            Test &amp; save
          </button>
          <button
            v-if="provider.has_personal_key"
            type="button"
            :disabled="busyProvider === provider.id"
            class="shrink-0 rounded-lg border border-white/10 px-3 py-2 text-[11px] font-black uppercase tracking-widest text-slate-300 hover:border-red-400/40 hover:text-red-300 disabled:opacity-40"
            @click="remove(provider)"
          >
            Remove
          </button>
        </form>
      </li>
    </ul>
  </section>
</template>
