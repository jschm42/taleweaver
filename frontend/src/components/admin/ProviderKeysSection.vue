<script setup lang="ts">
import { ref, computed } from 'vue'
import { ExternalLink, KeyRound, Search, Trash2 } from 'lucide-vue-next'
import KeyPolicySelect from './KeyPolicySelect.vue'
import ProviderKeyModal from './ProviderKeyModal.vue'
import { PROVIDERS, type ProviderMeta } from './providerCatalog'
import { useKeyPolicy } from './useKeyPolicy'
import { confirmDialog } from '@/composables/useDialogs'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

const props = defineProps<{
  configuredKeys: Record<string, { masked: string; is_env: boolean }>
  isSubmitting: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: { provider: string; api_key: string }): void
  (e: 'delete', provider: string): void
}>()

// Who pays per provider (server key, personal keys, disabled)
const keyPolicy = useKeyPolicy()

type Filter = 'all' | 'configured' | 'missing'
const activeFilter = ref<Filter>('all')
const searchQuery = ref('')
const activeProvider = ref<ProviderMeta | null>(null)

const isReady = (provider: ProviderMeta): boolean => Boolean(props.configuredKeys[provider.id]) || provider.id === 'ollama'

const filteredProviders = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return PROVIDERS.filter((p) => {
    if (q && !p.name.toLowerCase().includes(q) && !p.description.toLowerCase().includes(q)) return false
    if (activeFilter.value === 'configured' && !isReady(p)) return false
    if (activeFilter.value === 'missing' && isReady(p)) return false
    return true
  })
})

const configuredCount = computed(() => PROVIDERS.filter(isReady).length)

const filterOptions = computed<{ value: Filter; label: string; count: number }[]>(() => [
  { value: 'all', label: 'All', count: PROVIDERS.length },
  { value: 'configured', label: 'Ready', count: configuredCount.value },
  { value: 'missing', label: 'Missing', count: PROVIDERS.length - configuredCount.value },
])

function status(provider: ProviderMeta): { label: string; tone: 'warn' | 'accent' | 'info' | 'neutral'; title?: string } {
  const key = props.configuredKeys[provider.id]
  if (key?.is_env) return { label: 'Environment', tone: 'warn', title: 'Set by an environment variable; read-only here' }
  if (key) return { label: 'Configured', tone: 'accent' }
  if (provider.id === 'ollama') return { label: 'Local', tone: 'info' }
  return { label: 'Missing', tone: 'neutral' }
}

const handleSave = (apiKey: string) => {
  if (!activeProvider.value) return
  emit('save', { provider: activeProvider.value.id, api_key: apiKey })
  activeProvider.value = null
}

const handleDelete = async (provider: ProviderMeta): Promise<void> => {
  const confirmed = await confirmDialog({
    title: `Remove the ${provider.name} API key?`,
    message: 'Models that need this key stop working until a new key is saved.',
    confirmLabel: 'Remove key',
    danger: true,
  })
  if (confirmed) {
    emit('delete', provider.id)
  }
}

function resetFilters(): void {
  searchQuery.value = ''
  activeFilter.value = 'all'
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="API keys" description="Server keys for the AI providers, stored encrypted. Choose per provider who pays.">
      <template #badge>
        <UiBadge :tone="configuredCount > 1 ? 'accent' : 'warn'">{{ configuredCount }} ready</UiBadge>
      </template>
    </PageHeader>

    <UiCard :padded="false">
      <div class="flex flex-col gap-3 border-b border-wb-line p-3 sm:flex-row sm:items-center sm:justify-between">
        <UiSegmented v-model="activeFilter" :options="filterOptions" label="Show providers" />
        <div class="relative w-full sm:w-64">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-wb-faint" aria-hidden="true" />
          <UiInput v-model="searchQuery" type="search" size="sm" placeholder="Filter providers…" aria-label="Filter providers" class="pl-9" />
        </div>
      </div>

      <div v-if="filteredProviders.length === 0" class="p-4">
        <UiEmptyState :icon="Search" title="No providers match">
          <template #action>
            <UiButton size="sm" @click="resetFilters">Reset filters</UiButton>
          </template>
        </UiEmptyState>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-left">
          <thead>
            <tr class="border-b border-wb-line">
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Provider</th>
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Used for</th>
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Status</th>
              <th scope="col" class="wb-label px-5 py-3 !text-wb-muted" title="The server key or the players' own keys">Who pays</th>
              <th scope="col" class="px-5 py-3"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-wb-line">
            <tr v-for="provider in filteredProviders" :key="provider.id" class="hover:bg-wb-raised/50">
              <td class="px-5 py-3 align-middle">
                <div class="flex items-center gap-1.5">
                  <span class="wb-body font-medium text-wb-strong">{{ provider.name }}</span>
                  <a
                    v-if="provider.docsUrl"
                    :href="provider.docsUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-wb-faint hover:text-wb-info-text"
                    :aria-label="`Open the ${provider.name} key page`"
                  >
                    <ExternalLink class="h-3.5 w-3.5" aria-hidden="true" />
                  </a>
                </div>
                <p class="wb-hint max-w-md line-clamp-1">{{ provider.description }}</p>
              </td>
              <td class="px-5 py-3 align-middle">
                <div class="flex flex-wrap gap-1">
                  <UiBadge v-for="cap in provider.capabilities" :key="cap">{{ cap }}</UiBadge>
                </div>
              </td>
              <td class="whitespace-nowrap px-5 py-3 align-middle">
                <UiBadge :tone="status(provider).tone" :title="status(provider).title">{{ status(provider).label }}</UiBadge>
              </td>
              <td class="whitespace-nowrap px-5 py-3 align-middle">
                <KeyPolicySelect
                  v-if="provider.id !== 'ollama'"
                  :model-value="keyPolicy.policyFor(provider.id)"
                  :provider-name="provider.name"
                  :disabled="keyPolicy.isSaving.value"
                  @update:model-value="(value) => value && keyPolicy.setPolicy(provider.id, value)"
                />
                <span v-else class="wb-hint">Local</span>
              </td>
              <td class="whitespace-nowrap px-5 py-3 align-middle">
                <div class="flex items-center justify-end gap-1">
                  <UiIconButton
                    v-if="configuredKeys[provider.id] && !configuredKeys[provider.id].is_env"
                    :icon="Trash2"
                    :label="`Remove the ${provider.name} key`"
                    size="sm"
                    variant="danger"
                    @click="handleDelete(provider)"
                  />
                  <UiButton
                    v-if="provider.id !== 'ollama' && !configuredKeys[provider.id]?.is_env"
                    size="sm"
                    :variant="configuredKeys[provider.id] ? 'secondary' : 'primary'"
                    :icon="KeyRound"
                    @click="activeProvider = provider"
                  >
                    {{ configuredKeys[provider.id] ? 'Replace key' : 'Add key' }}
                  </UiButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </UiCard>

    <p v-if="keyPolicy.error.value" class="wb-body text-wb-danger-text" role="alert">{{ keyPolicy.error.value }}</p>
    <p class="wb-hint max-w-3xl">
      Who pays is saved as soon as you change it. With "own key optional" or "own key required", players enter their own key
      in their profile; "required" blocks the provider for players without a key, also for model passes that use it. Single
      users can get an exception on the Users page.
    </p>

    <ProviderKeyModal
      :provider="activeProvider"
      :has-key="Boolean(activeProvider && configuredKeys[activeProvider.id])"
      :is-submitting="isSubmitting"
      @close="activeProvider = null"
      @save="handleSave"
    />
  </div>
</template>
