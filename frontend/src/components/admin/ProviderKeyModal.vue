<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ExternalLink, Eye, EyeOff, KeyRound } from 'lucide-vue-next'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import type { ProviderMeta } from './providerCatalog'

/** Enter or replace the server key of one provider. */
const props = defineProps<{ provider: ProviderMeta | null; hasKey: boolean; isSubmitting: boolean }>()
const emit = defineEmits<{ close: []; save: [apiKey: string] }>()

const keyInput = ref('')
const showKey = ref(false)
const open = computed(() => props.provider !== null)

watch(
  () => props.provider,
  () => {
    keyInput.value = ''
    showKey.value = false
  },
)

function save(): void {
  if (keyInput.value.trim()) emit('save', keyInput.value.trim())
}

function handleOpenChange(value: boolean): void {
  if (!value) emit('close')
}
</script>

<template>
  <UiModal
    :open="open"
    :title="provider ? `${provider.name} API key` : ''"
    :description="provider?.description"
    @update:open="handleOpenChange"
  >
    <form v-if="provider" id="provider-key-form" class="space-y-4" @submit.prevent="save">
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="wb-hint">Used for</span>
        <UiBadge v-for="cap in provider.capabilities" :key="cap">{{ cap }}</UiBadge>
      </div>

      <UiNotice v-if="hasKey" tone="info">A key is already stored. Saving replaces it.</UiNotice>

      <UiField label="API key" hint="Stored encrypted on this server and only sent to this provider.">
        <div class="relative">
          <UiInput
            v-model="keyInput"
            :type="showKey ? 'text' : 'password'"
            :placeholder="provider.keyPrefix || 'Secret key'"
            autocomplete="off"
            spellcheck="false"
            class="pr-10 wb-mono"
            data-autofocus
          />
          <UiIconButton
            :icon="showKey ? EyeOff : Eye"
            :label="showKey ? 'Hide key' : 'Show key'"
            size="sm"
            class="absolute right-1 top-1/2 -translate-y-1/2"
            @click="showKey = !showKey"
          />
        </div>
      </UiField>

      <a
        v-if="provider.docsUrl"
        :href="provider.docsUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-1 wb-label !text-wb-info-text hover:underline"
      >
        Get a key from {{ provider.name }}
        <ExternalLink class="h-3.5 w-3.5" aria-hidden="true" />
      </a>
    </form>

    <template #footer>
      <UiButton @click="emit('close')">Cancel</UiButton>
      <UiButton
        variant="primary"
        type="submit"
        form="provider-key-form"
        :icon="KeyRound"
        :loading="isSubmitting"
        :disabled="!keyInput.trim()"
      >
        Save key
      </UiButton>
    </template>
  </UiModal>
</template>
