<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type KeyPolicy, type KeyPolicyMap } from '@/composables/useApi'
import KeyPolicySelect from './KeyPolicySelect.vue'

/** Per-user exceptions from the server-wide key policy (e.g. "server pays" for family). */
const props = defineProps<{
  userId: string
  overrides?: KeyPolicyMap | null
  personalKeyProviders?: string[]
}>()
const emit = defineEmits<{ (e: 'saved', overrides: KeyPolicyMap): void }>()

const providers = ref<Array<{ id: string, name: string }>>([])
const serverPolicy = ref<KeyPolicyMap>({})
const draft = ref<Record<string, KeyPolicy | ''>>({})
const isSaving = ref(false)
const message = ref('')

function serverLabel(provider: string): string {
  const labels: Record<string, string> = {
    server: 'server pays',
    user_optional: 'own key optional',
    user_required: 'own key required',
    disabled: 'disabled',
  }
  return labels[serverPolicy.value[provider] || 'server']
}

async function save(): Promise<void> {
  const overrides: KeyPolicyMap = {}
  for (const [provider, value] of Object.entries(draft.value)) {
    if (value) overrides[provider] = value
  }
  isSaving.value = true
  message.value = ''
  try {
    const result = await api.updateUserKeyPolicy(props.userId, overrides)
    message.value = 'Saved.'
    emit('saved', result.overrides)
  } catch (err: unknown) {
    message.value = err instanceof Error && err.message ? err.message : 'Failed to save.'
  } finally {
    isSaving.value = false
  }
}

onMounted(async () => {
  draft.value = { ...(props.overrides || {}) }
  try {
    const response = await api.getKeyPolicy()
    providers.value = response.providers
    serverPolicy.value = response.policy
  } catch {
    message.value = 'Failed to load the key policy.'
  }
})
</script>

<template>
  <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
    <div>
      <p class="text-xs font-bold uppercase tracking-wider text-slate-400">Who pays for this user</p>
      <p class="mt-0.5 text-[11px] text-slate-500">Exceptions from the server-wide policy. Saved separately.</p>
    </div>
    <div class="max-h-56 space-y-1.5 overflow-y-auto pr-1">
      <div v-for="provider in providers" :key="provider.id" class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="truncate text-xs font-bold text-white">
            {{ provider.name }}
            <span v-if="personalKeyProviders?.includes(provider.id)" class="ml-1 rounded bg-emerald-500/10 px-1.5 text-[10px] text-emerald-300">own key</span>
          </p>
          <p class="text-[10px] text-slate-500">Server default: {{ serverLabel(provider.id) }}</p>
        </div>
        <KeyPolicySelect v-model="draft[provider.id]" :provider-name="provider.name" inherit />
      </div>
    </div>
    <div class="flex items-center justify-end gap-3">
      <span v-if="message" class="text-[11px] text-slate-400">{{ message }}</span>
      <button
        type="button"
        :disabled="isSaving"
        class="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-[11px] font-bold text-slate-200 hover:bg-slate-700 disabled:opacity-50"
        @click="save"
      >
        {{ isSaving ? 'Saving...' : 'Save key policy' }}
      </button>
    </div>
  </div>
</template>
