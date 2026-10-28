<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Lock, Key, Unlock } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'
import PromptItemCard from './PromptItemCard.vue'
import { parseMetadata, formatIdToName } from './promptUtils'

/** Unlock prompt for a locked container or exit, shown inline at the end of the story feed. */
const props = defineProps<{
  open: boolean
  container: any
  inventoryItems: any[]
  busy?: boolean
  errorMessage?: string
  kind?: 'container' | 'exit'
}>()

const emit = defineEmits<{
  close: []
  submitCode: [code: string]
  useKeyItem: [itemId: string]
  unlockDirect: []
}>()

const codeInput = ref('')
const codeInputRef = ref<HTMLInputElement | null>(null)

const resolvedMetadata = computed(() => parseMetadata(props.container?.metadata_json))

/** Reads an unlock field from the entity, its parsed metadata_json or its metadata object. */
const readLockField = (field: string): string => {
  return String(
    props.container?.[field]
    || resolvedMetadata.value[field]
    || props.container?.metadata?.[field]
    || ''
  ).trim()
}

const requiredCode = computed(() => readLockField('code_to_unlock'))
const requiredItemId = computed(() => readLockField('item_to_unlock').toUpperCase())
const requiredRule = computed(() => readLockField('rule_to_unlock'))
const unlockExpression = computed(() => readLockField('unlock_expression'))

const effectiveKind = computed(() => props.kind || (props.container?.exit_type ? 'exit' : 'container'))
const entityNoun = computed(() => (effectiveKind.value === 'exit' ? 'exit' : 'container'))
const effectiveTitle = computed(() => props.container?.name || props.container?.label || (effectiveKind.value === 'exit' ? 'Exit' : 'Container'))
const effectiveHeader = computed(() => (effectiveKind.value === 'exit' ? 'Locked Exit' : 'Locked Container'))
const effectiveDescription = computed(() => String(props.container?.description || props.container?.lock_description || '').trim())
const imageUrl = computed(() => getImageUrl(props.container?.image_url) || null)

// Find matching key item in inventory
const matchingInventoryKey = computed(() => {
  if (!requiredItemId.value) return null
  return props.inventoryItems.find(item => {
    const itemId = String(item?.id || '').trim().toUpperCase()
    const itemName = String(item?.name || '').trim().toUpperCase()
    return itemId === requiredItemId.value || itemName === requiredItemId.value
  })
})

const handleCodeSubmit = () => {
  if (!codeInput.value.trim() || props.busy) return
  emit('submitCode', codeInput.value.trim())
}

const handleUseKey = () => {
  if (!matchingInventoryKey.value || props.busy) return
  emit('useKeyItem', matchingInventoryKey.value.id || requiredItemId.value)
}

const handleUnlockDirect = () => {
  if (props.busy) return
  emit('unlockDirect')
}

// Fresh input whenever the panel opens or switches to another lock.
const onRevealed = () => {
  codeInput.value = ''
  codeInputRef.value?.focus({ preventScroll: true })
}

// A wrong code keeps the panel open: select the input so the next try replaces it.
watch(() => props.errorMessage, (message) => {
  if (message) nextTick(() => codeInputRef.value?.select())
})
</script>

<template>
  <InlinePromptPanel
    :open="open && !!container"
    :label="effectiveHeader"
    :title="effectiveTitle"
    :description="effectiveDescription"
    :image-url="imageUrl"
    :busy="busy"
    :reveal-key="String(container?.id || '')"
    @close="emit('close')"
    @revealed="onRevealed"
  >
    <template #label-icon><Lock class="w-3 h-3" /></template>

    <!-- CODE REQUIREMENT -->
    <form v-if="requiredCode" class="flex gap-2" @submit.prevent="handleCodeSubmit">
      <input
        ref="codeInputRef"
        v-model="codeInput"
        type="text"
        placeholder="Enter code..."
        maxlength="32"
        autocomplete="off"
        aria-label="Combination code"
        :disabled="busy"
        class="tw-prompt-input"
      />
      <button type="submit" class="tw-prompt-action" :disabled="busy || !codeInput.trim()">
        <Unlock class="w-4 h-4" />
        <span>Unlock</span>
      </button>
    </form>

    <!-- ITEM REQUIREMENT -->
    <template v-else-if="requiredItemId">
      <PromptItemCard v-if="matchingInventoryKey" :item="matchingInventoryKey">
        <button type="button" class="tw-prompt-action" :disabled="busy" @click="handleUseKey">
          <Key class="w-4 h-4" />
          <span>Use Item</span>
        </button>
      </PromptItemCard>
      <p v-else class="tw-prompt-hint">
        This {{ entityNoun }} requires an item you do not possess ({{ formatIdToName(requiredItemId) }}).
      </p>
    </template>

    <!-- RULE/PUZZLE REQUIREMENT -->
    <p v-else-if="requiredRule && !unlockExpression" class="tw-prompt-hint">
      This {{ entityNoun }} cannot be opened directly. You must satisfy a condition or solve a puzzle in the world first.
    </p>

    <!-- SCRIPT GUARD / DIRECT UNLOCK -->
    <div v-else class="flex items-center justify-between gap-3">
      <p class="tw-prompt-hint">
        {{ unlockExpression ? `This ${entityNoun} is held by a mechanism or condition in the world.` : 'The way is currently barred. You can attempt to unlock or open it.' }}
      </p>
      <button type="button" class="tw-prompt-action shrink-0" :disabled="busy" @click="handleUnlockDirect">
        <Unlock class="w-4 h-4" />
        <span>Attempt Unlock</span>
      </button>
    </div>

    <p v-if="errorMessage" class="tw-choice-error">{{ errorMessage }}</p>
  </InlinePromptPanel>
</template>
