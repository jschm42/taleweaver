<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, Copy, KeyRound, Plus, ShieldOff } from 'lucide-vue-next'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiBadge, { type BadgeTone } from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import McpTokenCreateModal from '@/components/admin/McpTokenCreateModal.vue'
import McpTokenRevealModal from '@/components/admin/McpTokenRevealModal.vue'
import { useConfirm } from '@/composables/useDialogs'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import {
  MCP_FEATURE_META,
  mcpSettingsService,
  type McpSettings,
  type McpTokenCreated,
  type McpTokenRecord,
  type McpTokenStatus,
} from '@/services/mcpSettingsService'

export interface AdminUserOption {
  id: string
  username: string
  role: string
}

defineProps<{
  usersList: AdminUserOption[]
}>()

const toast = useToast()
const confirm = useConfirm()

const saved = ref<McpSettings | null>(null)
const tokens = ref<McpTokenRecord[]>([])
const loadError = ref('')
const isLoading = ref(true)
const revokingId = ref<string | null>(null)
const copiedTarget = ref<'url' | 'snippet' | null>(null)

const isCreateOpen = ref(false)
const isRevealOpen = ref(false)
const revealedToken = ref('')

const { draft: settings, isDirty, changedCount, isSaving, reset, commit } = useDraft(() => saved.value)

const endpointUrl = computed(() => {
  const path = settings.value?.endpoint_path || '/mcp'
  if (typeof window === 'undefined') {
    return path
  }
  return `${window.location.origin}${path}`
})

const clientConfigSnippet = computed(() =>
  JSON.stringify(
    {
      mcpServers: {
        taleweaver: {
          type: 'http',
          url: endpointUrl.value,
          headers: {
            Authorization: 'Bearer <your-mcp-token>',
          },
        },
      },
    },
    null,
    2,
  ),
)

const STATUS_TONE: Record<McpTokenStatus, BadgeTone> = {
  active: 'accent',
  expired: 'warn',
  revoked: 'neutral',
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function formatDate(iso: string | null): string {
  if (!iso) {
    return 'Never'
  }
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) {
    return iso
  }
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function scopeLabel(token: McpTokenRecord): string {
  if (!token.allowed_features) {
    return 'All enabled features'
  }
  const count = token.allowed_features.length
  return count === 1 ? '1 feature' : `${count} features`
}

async function copyText(text: string, target: 'url' | 'snippet'): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    copiedTarget.value = target
    window.setTimeout(() => {
      if (copiedTarget.value === target) {
        copiedTarget.value = null
      }
    }, 2000)
  } catch {
    toast.error('Could not copy to clipboard.')
  }
}

async function loadAll(): Promise<void> {
  isLoading.value = true
  loadError.value = ''
  try {
    const [loadedSettings, loadedTokens] = await Promise.all([
      mcpSettingsService.load(),
      mcpSettingsService.listTokens(),
    ])
    saved.value = loadedSettings
    tokens.value = loadedTokens
  } catch (err) {
    loadError.value = errorMessage(err)
  } finally {
    isLoading.value = false
  }
}

async function save(): Promise<void> {
  try {
    let updated: McpSettings | null = null
    await commit(async (draft) => {
      if (!draft) {
        return
      }
      updated = await mcpSettingsService.save({
        enabled: draft.enabled,
        features: { ...draft.features },
        allow_destructive: draft.allow_destructive,
        allow_cross_user_access: draft.allow_cross_user_access,
      })
    })
    if (updated) {
      saved.value = updated
    }
    toast.success('MCP settings saved.')
  } catch (err) {
    toast.error(errorMessage(err))
  }
}

function handleTokenCreated(created: McpTokenCreated): void {
  tokens.value = [created.token, ...tokens.value]
  revealedToken.value = created.plain_token
  isRevealOpen.value = true
  toast.success(`Access token "${created.token.name}" created.`)
}

function handleRevealClosed(): void {
  revealedToken.value = ''
}

async function revokeToken(token: McpTokenRecord): Promise<void> {
  const ok = await confirm({
    title: `Revoke token "${token.name}"?`,
    message: 'Clients using this token will immediately lose access to the MCP server.',
    confirmLabel: 'Revoke token',
    danger: true,
  })
  if (!ok) {
    return
  }
  revokingId.value = token.id
  try {
    const updated = await mcpSettingsService.revokeToken(token.id)
    tokens.value = tokens.value.map((item) => (item.id === updated.id ? updated : item))
    toast.success(`Token "${token.name}" revoked.`)
  } catch (err) {
    toast.error(errorMessage(err))
  } finally {
    revokingId.value = null
  }
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <div class="space-y-6">
    <PageHeader
      title="MCP Server"
      description="Connect external AI agents to inspect sessions and adventures, edit templates, and run generation pipelines over Model Context Protocol."
    >
      <template #badge>
        <UiBadge v-if="saved" :tone="saved.enabled ? 'accent' : 'neutral'">
          {{ saved.enabled ? 'Active' : 'Disabled' }}
        </UiBadge>
      </template>
    </PageHeader>

    <p v-if="loadError" class="wb-body text-wb-danger-text" role="alert">{{ loadError }}</p>
    <div v-else-if="isLoading || !settings" class="flex justify-center py-10">
      <UiSpinner label="Loading MCP settings" />
    </div>

    <template v-else>
      <UiCard title="Endpoint">
        <div class="space-y-5">
          <UiToggle
            v-model="settings.enabled"
            label="Enable MCP endpoint"
            description="Off: /mcp rejects all client connections and exposes no tools or resources."
          />

          <UiField
            label="Endpoint URL"
            hint="Configure external Streamable HTTP MCP clients with this URL and a Bearer access token."
          >
            <div class="flex flex-col gap-2 sm:flex-row">
              <UiInput
                :model-value="endpointUrl"
                readonly
                mono
                class="flex-1"
                @focus="($event.target as HTMLInputElement).select()"
              />
              <UiButton
                variant="secondary"
                :icon="copiedTarget === 'url' ? Check : Copy"
                @click="copyText(endpointUrl, 'url')"
              >
                {{ copiedTarget === 'url' ? 'Copied' : 'Copy URL' }}
              </UiButton>
            </div>
          </UiField>

          <UiDisclosure label="Client configuration snippet" hint="JSON example for Claude Code or Cursor">
            <div class="space-y-2">
              <pre
                class="overflow-x-auto rounded-md border border-wb-line bg-wb-raised p-3 wb-mono text-wb-body"
              >{{ clientConfigSnippet }}</pre>
              <div class="flex justify-end">
                <UiButton
                  size="sm"
                  variant="secondary"
                  :icon="copiedTarget === 'snippet' ? Check : Copy"
                  @click="copyText(clientConfigSnippet, 'snippet')"
                >
                  {{ copiedTarget === 'snippet' ? 'Copied' : 'Copy JSON' }}
                </UiButton>
              </div>
            </div>
          </UiDisclosure>
        </div>
      </UiCard>

      <UiCard
        title="Features & safety"
        description="Disabled feature groups are hidden from MCP discovery and blocked on execution."
      >
        <div class="space-y-5">
          <div class="divide-y divide-wb-line">
            <div
              v-for="item in MCP_FEATURE_META"
              :key="item.key"
              class="py-3 first:pt-0 last:pb-0"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 space-y-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="wb-label !text-wb-strong">{{ item.label }}</span>
                    <UiBadge v-if="item.quotaLabel" :tone="item.quotaTone">{{ item.quotaLabel }}</UiBadge>
                  </div>
                  <p class="wb-hint">{{ item.description }}</p>
                </div>
                <UiToggle
                  v-model="settings.features[item.key]"
                  :label="item.label"
                  hide-label
                />
              </div>
            </div>
          </div>

          <UiDisclosure label="Safety & scope" hint="Destructive actions and cross-user visibility">
            <div class="space-y-4 border-t border-wb-line pt-4">
              <UiToggle
                v-model="settings.allow_destructive"
                label="Allow destructive deletes"
                description="Allows deleting entire adventure templates via MCP. Scene and entity deletes inside change sets are governed by Adventure editing."
              />
              <UiToggle
                v-model="settings.allow_cross_user_access"
                label="Allow cross-user inspection"
                description="Admin-bound tokens may inspect sessions and adventures owned by other users."
              />
            </div>
          </UiDisclosure>
        </div>
      </UiCard>

      <UiCard
        title="Access tokens"
        description="Bearer tokens authenticate external MCP clients under a TaleWeaver user account."
        :padded="tokens.length === 0"
      >
        <template #actions>
          <UiButton variant="primary" size="sm" :icon="Plus" @click="isCreateOpen = true">
            Create token
          </UiButton>
        </template>

        <UiEmptyState
          v-if="tokens.length === 0"
          :icon="KeyRound"
          title="No access tokens yet"
          description="Create a bearer token so an external MCP client can connect."
        >
          <template #action>
            <UiButton variant="primary" :icon="Plus" @click="isCreateOpen = true">
              Create token
            </UiButton>
          </template>
        </UiEmptyState>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left">
            <thead>
              <tr class="border-b border-wb-line">
                <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Token</th>
                <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Acting user</th>
                <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Scope</th>
                <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Activity</th>
                <th scope="col" class="wb-label px-5 py-3 !text-wb-muted">Status</th>
                <th scope="col" class="px-5 py-3"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-wb-line">
              <tr v-for="token in tokens" :key="token.id" class="hover:bg-wb-raised/50">
                <td class="px-5 py-3">
                  <div class="wb-body font-medium text-wb-strong">{{ token.name }}</div>
                  <div class="wb-mono text-wb-faint">{{ token.token_prefix }}…</div>
                </td>
                <td class="px-5 py-3">
                  <div class="flex flex-wrap items-center gap-1.5">
                    <span class="wb-body text-wb-body">{{ token.username }}</span>
                    <UiBadge v-if="token.user_role === 'admin'" tone="info">admin</UiBadge>
                  </div>
                </td>
                <td class="px-5 py-3">
                  <span class="wb-body text-wb-body">{{ scopeLabel(token) }}</span>
                </td>
                <td class="px-5 py-3">
                  <div class="wb-hint">Last used: {{ formatDate(token.last_used_at) }}</div>
                  <div class="wb-hint">Expires: {{ formatDate(token.expires_at) }}</div>
                </td>
                <td class="px-5 py-3">
                  <UiBadge :tone="STATUS_TONE[token.status]">{{ token.status }}</UiBadge>
                </td>
                <td class="px-5 py-3 text-right">
                  <UiButton
                    v-if="token.status !== 'revoked'"
                    variant="ghost"
                    size="sm"
                    :icon="ShieldOff"
                    :loading="revokingId === token.id"
                    class="!text-wb-danger-text"
                    @click="revokeToken(token)"
                  >
                    Revoke
                  </UiButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UiCard>
    </template>

    <McpTokenCreateModal
      v-model:open="isCreateOpen"
      :users-list="usersList"
      @created="handleTokenCreated"
    />

    <McpTokenRevealModal
      v-model:open="isRevealOpen"
      :plain-token="revealedToken"
      @close="handleRevealClosed"
    />

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
