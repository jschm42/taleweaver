<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Lock, Key, Unlock, X } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'
import PromptItemTile from './PromptItemTile.vue'
import { parseMetadata } from './promptUtils'

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
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
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

// The player picks the item to try; the backend decides whether it fits, so the
// required item is never revealed or preselected here.
const itemId = (item: any): string => String(item?.id || '').trim()
const candidateItems = computed(() => (props.inventoryItems || []).filter(item => itemId(item)))

/** Item placed in the lock slot; picking another item replaces it. */
const chosenId = ref('')
const chosenItem = computed(() => candidateItems.value.find(item => itemId(item) === chosenId.value) || null)
const choose = (item: any) => {
  if (props.busy) return
  chosenId.value = chosenId.value === itemId(item) ? '' : itemId(item)
}

const handleCodeSubmit = () => {
  if (!codeInput.value.trim() || props.busy) return
  emit('submitCode', codeInput.value.trim())
}

const handleUseItem = () => {
  if (!chosenItem.value || props.busy) return
  emit('itemLeave')
  emit('useKeyItem', itemId(chosenItem.value))
}

const handleUnlockDirect = () => {
  if (props.busy) return
  emit('unlockDirect')
}

// Fresh input whenever the panel opens or switches to another lock.
const onRevealed = () => {
  codeInput.value = ''
  chosenId.value = ''
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
      <template v-if="candidateItems.length">
        <!-- Lock slot -->
        <div class="tw-prompt-bench">
          <PromptItemTile
            v-if="chosenItem"
            :item="chosenItem"
            selected
            large
            :disabled="busy"
            :title="`Remove ${chosenItem.name || chosenItem.id}`"
            @click="choose(chosenItem)"
            @mouseenter="emit('itemHover', { ...chosenItem, entity_type: 'ITEM' }, $event)"
            @mouseleave="emit('itemLeave')"
          >
            <span class="tw-prompt-tile-check"><X class="w-3 h-3" stroke-width="3" /></span>
          </PromptItemTile>
          <span v-else class="tw-prompt-slot">+</span>
        </div>

        <p class="tw-prompt-group">Inventory</p>
        <div class="grid grid-cols-5 sm:grid-cols-8 gap-2 max-h-44 overflow-y-auto p-0.5">
          <PromptItemTile
            v-for="item in candidateItems"
            :key="itemId(item)"
            :item="item"
            :dimmed="itemId(item) === chosenId"
            :disabled="busy"
            :title="itemId(item) === chosenId ? `Remove ${item.name || item.id}` : `Try ${item.name || item.id}`"
            @click="choose(item)"
            @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
            @mouseleave="emit('itemLeave')"
          />
        </div>

        <div class="flex items-center justify-between gap-3">
          <p class="tw-prompt-hint">
            {{ chosenItem ? `Try ${chosenItem.name || chosenItem.id} on this ${entityNoun}.` : `Choose an item to try on this ${entityNoun}.` }}
          </p>
          <button type="button" class="tw-prompt-action shrink-0" :disabled="!chosenItem || busy" @click="handleUseItem">
            <Key class="w-4 h-4" />
            <span>Use</span>
          </button>
        </div>
      </template>
      <p v-else class="tw-prompt-hint">
        This {{ entityNoun }} needs something to open it, but you carry nothing you could try.
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
