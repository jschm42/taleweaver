<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Lock, Unlock, Check } from 'lucide-vue-next'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'
import { parseMetadata } from './promptUtils'
import { stateLabel } from '../immersive/switchState'

/** Gate (code, item or rule) of a locked switch transition, shown inline at the end of the story feed. */
const props = defineProps<{
  open: boolean
  switchEntity: any
  targetState: string
  inventoryItems: any[]
  busy?: boolean
  errorMessage?: string
}>()

const emit = defineEmits<{
  close: []
  submitCode: [code: string]
  useKeyItem: [itemId: string]
}>()

const codeInput = ref('')
const codeInputRef = ref<HTMLInputElement | null>(null)
const selectedItemId = ref<string>('')

const brokenImages = ref<Record<string, boolean>>({})
const itemImageUrl = (item: any): string => {
  const path = String(item?.image_url || '')
  return path && !brokenImages.value[path] ? getImageUrl(path) : ''
}
const handleImageError = (item: any) => {
  const path = String(item?.image_url || '')
  if (path) brokenImages.value[path] = true
}

const resolvedMetadata = computed(() => parseMetadata(props.switchEntity?.metadata_json))
const nestedSwitch = computed(() => {
  const meta = resolvedMetadata.value
  return (meta.switch && typeof meta.switch === 'object') ? meta.switch : {}
})

const switchTransitions = computed<any[]>(() => {
  const meta = resolvedMetadata.value
  if (Array.isArray(nestedSwitch.value.transitions) && nestedSwitch.value.transitions.length > 0) return nestedSwitch.value.transitions
  if (Array.isArray(meta.switch_transitions)) return meta.switch_transitions
  if (Array.isArray(props.switchEntity?.switch_transitions)) return props.switchEntity.switch_transitions
  return []
})

const switchInitialState = computed(() => {
  const meta = resolvedMetadata.value
  return String(nestedSwitch.value.initial_state || meta.switch_initial_state || props.switchEntity?.switch_initial_state || '').trim().toUpperCase()
})

const transitionState = (t: any, ...keys: string[]): string => {
  const value = keys.map(key => t[key]).find(Boolean)
  return String(value || '').trim().toUpperCase()
}

/** The transition into the target state: an exact `from` match wins over a wildcard one. */
const activeTransition = computed(() => {
  const currentState = String(props.switchEntity?.switch_state || switchInitialState.value || '').trim().toUpperCase()
  const targetState = String(props.targetState || '').trim().toUpperCase()
  const candidates = switchTransitions.value.filter(
    (t: any) => t && typeof t === 'object' && transitionState(t, 'to', 'to_state') === targetState,
  )
  const exactMatch = candidates.find((t: any) => transitionState(t, 'from', 'from_state') === currentState)
  const wildcardMatch = candidates.find((t: any) => !transitionState(t, 'from', 'from_state'))
  return exactMatch || wildcardMatch || null
})

const gates = computed(() => activeTransition.value?.gates || {})
const requiredCode = computed(() => String(gates.value.code || '').trim())
const requiredItemId = computed(() => String(gates.value.item || '').trim().toUpperCase())
const requiredRule = computed(() => String(gates.value.rule || '').trim())
const imageUrl = computed(() => getImageUrl(props.switchEntity?.image_url) || null)

// Only usable items (no switches, containers or fixed objects) can be offered.
const usableItems = computed(() => {
  return (props.inventoryItems || []).filter((item: any) => {
    if (!item) return false
    const type = String(item.item_type || '').trim().toUpperCase()
    return type !== 'SWITCH' && type !== 'CONTAINER' && item.is_portable !== false
  })
})

const selectedItem = computed(() => {
  if (!selectedItemId.value) return null
  return usableItems.value.find((it: any) => String(it.id || '') === selectedItemId.value) || null
})

const selectItem = (itemId: string) => {
  if (props.busy) return
  selectedItemId.value = itemId
}

const handleCodeSubmit = () => {
  if (!codeInput.value.trim() || props.busy) return
  emit('submitCode', codeInput.value.trim())
}

const handleActivate = () => {
  if (!selectedItem.value || props.busy) return
  emit('useKeyItem', selectedItem.value.id)
}

const onRevealed = () => {
  codeInput.value = ''
  selectedItemId.value = ''
  codeInputRef.value?.focus({ preventScroll: true })
}

watch(() => props.errorMessage, (message) => {
  if (message) nextTick(() => codeInputRef.value?.select())
})
</script>

<template>
  <InlinePromptPanel
    :open="open && !!switchEntity"
    label="Locked Transition"
    :title="switchEntity?.name || 'Switch'"
    :description="switchEntity?.description || ''"
    :image-url="imageUrl"
    :busy="busy"
    :reveal-key="`${switchEntity?.id || ''}:${targetState}`"
    @close="emit('close')"
    @revealed="onRevealed"
  >
    <template #label-icon><Lock class="w-3 h-3" /></template>
    <template #aside>
      <p class="tw-prompt-hint">Flipping to <span class="tw-prompt-chip">{{ stateLabel(switchEntity, targetState) }}</span></p>
    </template>

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
      <p v-if="usableItems.length === 0" class="tw-prompt-hint">Your inventory contains no usable items.</p>
      <template v-else>
        <p class="tw-prompt-hint">Choose an item from your inventory to flip this switch.</p>
        <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-56 overflow-y-auto p-0.5">
          <button
            v-for="item in usableItems"
            :key="item.id"
            type="button"
            :disabled="busy"
            class="tw-prompt-tile"
            :class="{ 'is-selected': selectedItemId === item.id }"
            :title="item.name || item.id"
            @click="selectItem(item.id)"
          >
            <img v-if="itemImageUrl(item)" :src="itemImageUrl(item)" class="w-full h-full object-cover object-top" @error="handleImageError(item)" />
            <i v-else :class="['ra text-2xl', getItemIcon(item.item_type ?? undefined), getTypeColor(item.item_type ?? undefined)]"></i>
            <span v-if="selectedItemId === item.id" class="tw-prompt-tile-check">
              <Check class="w-3 h-3" stroke-width="3" />
            </span>
            <span class="tw-prompt-tile-caption">{{ item.name || item.id }}</span>
          </button>
        </div>
        <div class="flex justify-end">
          <button type="button" class="tw-prompt-action" :disabled="busy || !selectedItem" @click="handleActivate">
            <Unlock class="w-4 h-4" />
            <span>Activate</span>
          </button>
        </div>
      </template>
    </template>

    <!-- RULE/PUZZLE REQUIREMENT -->
    <p v-else-if="requiredRule" class="tw-prompt-hint">
      This switch transition cannot be triggered directly. You must satisfy a condition or solve a puzzle in the world first.
    </p>

    <p v-if="errorMessage" class="tw-choice-error">{{ errorMessage }}</p>
  </InlinePromptPanel>
</template>
