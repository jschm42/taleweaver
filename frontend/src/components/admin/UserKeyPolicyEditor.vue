<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type KeyPolicy, type KeyPolicyMap } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import KeyPolicySelect from './KeyPolicySelect.vue'

/** Per-user exceptions from the server-wide key policy (e.g. "server pays" for family). */
const props = defineProps<{
  userId: string
  overrides?: KeyPolicyMap | null
  personalKeyProviders?: string[]
}>()
const emit = defineEmits<{ (e: 'saved', overrides: KeyPolicyMap): void }>()

const toast = useToast()
const providers = ref<Array<{ id: string, name: string }>>([])
const serverPolicy = ref<KeyPolicyMap>({})
const draft = ref<Record<string, KeyPolicy | ''>>({})
const isSaving = ref(false)
const loadError = ref('')

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
  try {
    const result = await api.updateUserKeyPolicy(props.userId, overrides)
    toast.success('Key policy saved.')
    emit('saved', result.overrides)
  } catch (err: unknown) {
    toast.error(err instanceof Error && err.message ? err.message : 'Failed to save the key policy.')
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
    loadError.value = 'Failed to load the key policy.'
  }
})
</script>

<template>
  <section class="space-y-3 border-t border-wb-line pt-4">
    <div>
      <h3 class="wb-subheading">Who pays for this user</h3>
      <p class="wb-hint mt-0.5">Exceptions from the server-wide policy. Saved separately from the account.</p>
    </div>
    <p v-if="loadError" class="wb-hint !text-wb-danger-text" role="alert">{{ loadError }}</p>
    <ul class="max-h-56 divide-y divide-wb-line overflow-y-auto pr-1">
      <li v-for="provider in providers" :key="provider.id" class="flex items-center justify-between gap-3 py-2">
        <div class="min-w-0">
          <p class="wb-label !text-wb-strong flex items-center gap-1.5 truncate">
            {{ provider.name }}
            <UiBadge v-if="personalKeyProviders?.includes(provider.id)" tone="accent">own key</UiBadge>
          </p>
          <p class="wb-hint">Server default: {{ serverLabel(provider.id) }}</p>
        </div>
        <KeyPolicySelect v-model="draft[provider.id]" :provider-name="provider.name" inherit />
      </li>
    </ul>
    <div class="flex justify-end">
      <UiButton size="sm" :loading="isSaving" @click="save">Save key policy</UiButton>
    </div>
  </section>
</template>
