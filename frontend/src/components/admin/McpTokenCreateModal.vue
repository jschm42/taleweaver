<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiRadioCards, { type RadioCardOption } from '@/components/ui/UiRadioCards.vue'
import UiSelect, { type SelectOption } from '@/components/ui/UiSelect.vue'
import type { AdminUserOption } from '@/components/admin/McpSection.vue'
import {
  MCP_FEATURE_META,
  mcpSettingsService,
  type McpFeatureKey,
  type McpTokenCreated,
} from '@/services/mcpSettingsService'
import { authState } from '@/store/auth'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  usersList: AdminUserOption[]
}>()

const emit = defineEmits<{
  created: [result: McpTokenCreated]
}>()

type ScopeMode = 'inherit' | 'custom'

const EXPIRATION_OPTIONS: SelectOption[] = [
  { value: 'never', label: 'Never expires' },
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
  { value: '365', label: '1 year' },
]

const SCOPE_OPTIONS: RadioCardOption<ScopeMode>[] = [
  {
    value: 'inherit',
    label: 'Inherit server settings',
    description: 'Uses all features currently enabled on the server.',
  },
  {
    value: 'custom',
    label: 'Custom subset',
    description: 'Restrict this token to specific feature groups.',
  },
]

const READ_ONLY_KEYS: McpFeatureKey[] = ['read_adventures', 'read_sessions', 'diagnostics']

const name = ref('')
const userId = ref('')
const expiration = ref<string>('never')
const scopeMode = ref<ScopeMode>('inherit')
const selectedFeatures = ref<Record<McpFeatureKey, boolean>>({
  read_adventures: true,
  read_sessions: true,
  edit_adventures: false,
  generate_adventures: false,
  generate_media: false,
  diagnostics: true,
})
const errorText = ref('')
const isSubmitting = ref(false)

const userOptions = computed<SelectOption[]>(() =>
  props.usersList.map((u) => ({
    value: u.id,
    label: u.role === 'admin' ? `${u.username} (admin)` : u.username,
  })),
)

const selectedFeatureList = computed<McpFeatureKey[]>(() =>
  MCP_FEATURE_META.map((item) => item.key).filter((key) => selectedFeatures.value[key]),
)

function resetForm(): void {
  name.value = ''
  userId.value = authState.user?.id || props.usersList[0]?.id || ''
  expiration.value = 'never'
  scopeMode.value = 'inherit'
  selectedFeatures.value = {
    read_adventures: true,
    read_sessions: true,
    edit_adventures: false,
    generate_adventures: false,
    generate_media: false,
    diagnostics: true,
  }
  errorText.value = ''
}

watch(open, (isOpen) => {
  if (isOpen) {
    resetForm()
  }
})

function applyReadOnlyPreset(): void {
  for (const item of MCP_FEATURE_META) {
    selectedFeatures.value[item.key] = READ_ONLY_KEYS.includes(item.key)
  }
}

async function submit(): Promise<void> {
  errorText.value = ''
  const cleanName = name.value.trim()
  if (!cleanName) {
    errorText.value = 'Enter a name to identify this token.'
    return
  }
  if (scopeMode.value === 'custom' && selectedFeatureList.value.length === 0) {
    errorText.value = 'Select at least one feature group or inherit server settings.'
    return
  }
  isSubmitting.value = true
  try {
    const expiresDays = expiration.value === 'never' ? null : Number(expiration.value)
    const created = await mcpSettingsService.createToken({
      name: cleanName,
      user_id: userId.value || null,
      allowed_features: scopeMode.value === 'custom' ? selectedFeatureList.value : null,
      expires_in_days: expiresDays,
    })
    open.value = false
    emit('created', created)
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : String(err)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <UiModal
    v-model:open="open"
    title="Create MCP access token"
    description="Tokens authenticate external MCP clients under the selected user account."
    :persistent="isSubmitting"
  >
    <form class="space-y-4" @submit.prevent="submit">
      <UiField label="Token name" required hint="A label to recognize where this token is used.">
        <UiInput
          v-model="name"
          placeholder="Claude Code Laptop"
          maxlength="100"
          :disabled="isSubmitting"
        />
      </UiField>

      <div class="grid gap-4 sm:grid-cols-2">
        <UiField label="Acting user">
          <UiSelect v-model="userId" :options="userOptions" :disabled="isSubmitting" />
        </UiField>
        <UiField label="Expiration">
          <UiSelect v-model="expiration" :options="EXPIRATION_OPTIONS" :disabled="isSubmitting" />
        </UiField>
      </div>

      <UiField label="Feature scope">
        <UiRadioCards v-model="scopeMode" label="Feature scope" :options="SCOPE_OPTIONS" />
      </UiField>

      <div v-if="scopeMode === 'custom'" class="space-y-3 rounded-xl border border-wb-line bg-wb-raised p-4">
        <div class="flex items-center justify-between gap-2">
          <span class="wb-label">Allowed features</span>
          <UiButton type="button" size="sm" variant="ghost" @click="applyReadOnlyPreset">
            Read-only preset
          </UiButton>
        </div>
        <div class="space-y-2.5">
          <UiCheckbox
            v-for="item in MCP_FEATURE_META"
            :key="item.key"
            v-model="selectedFeatures[item.key]"
            :label="item.label"
            :description="item.description"
            :disabled="isSubmitting"
          />
        </div>
      </div>

      <p v-if="errorText" class="wb-body text-wb-danger-text" role="alert">{{ errorText }}</p>
    </form>

    <template #footer>
      <UiButton variant="ghost" :disabled="isSubmitting" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :loading="isSubmitting" @click="submit">Create token</UiButton>
    </template>
  </UiModal>
</template>
