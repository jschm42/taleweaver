<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Lock, Key, Unlock, X } from 'lucide-vue-next'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

/**
 * Unlock prompt for a locked container or exit, shown inline at the end of the story feed
 * (like DialogChoicePanel). It is styled by the active dialog skin and can be dismissed.
 */
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
const panelRef = ref<HTMLElement | null>(null)
const codeInputRef = ref<HTMLInputElement | null>(null)

const brokenImages = ref<Record<string, boolean>>({})
const showImage = (path?: string | null) => !!path && !brokenImages.value[path]
const handleImageError = (path: string) => {
  if (path) brokenImages.value[path] = true
}

const resolvedMetadata = computed(() => {
  let meta: any = props.container?.metadata_json
  if (typeof meta === 'string') {
    try {
      meta = JSON.parse(meta)
    } catch {
      meta = {}
    }
  }
  return meta && typeof meta === 'object' ? meta : {}
})

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

// Helper to format ID to readable name (e.g. BRONZE_KEY -> Bronze Key)
const formatIdToName = (id: string): string => {
  return id
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

// Find matching key item in inventory
const matchingInventoryKey = computed(() => {
  if (!requiredItemId.value) return null
  return props.inventoryItems.find(item => {
    const itemId = String(item?.id || '').trim().toUpperCase()
    const itemName = String(item?.name || '').trim().toUpperCase()
    return itemId === requiredItemId.value || itemName === requiredItemId.value
  })
})

const hasRequiredKey = computed(() => !!matchingInventoryKey.value)

const handleCodeSubmit = () => {
  if (!codeInput.value.trim() || props.busy) return
  emit('submitCode', codeInput.value.trim())
}

const handleUseKey = () => {
  if (!hasRequiredKey.value || props.busy) return
  emit('useKeyItem', matchingInventoryKey.value.id || requiredItemId.value)
}

const handleUnlockDirect = () => {
  if (props.busy) return
  emit('unlockDirect')
}

const close = () => {
  if (props.busy) return
  emit('close')
}

const onKeyDown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape' || !props.open) return
  close()
}

const revealPanel = () => {
  nextTick(() => {
    panelRef.value?.scrollIntoView({ block: 'end', behavior: 'smooth' })
    codeInputRef.value?.focus({ preventScroll: true })
  })
}

// Fresh input and scroll into view whenever the panel opens or switches to another lock.
watch(() => [props.open, props.container?.id], () => {
  if (!props.open) return
  codeInput.value = ''
  revealPanel()
})

// A wrong code keeps the panel open: select the input so the next try replaces it.
watch(() => props.errorMessage, (message) => {
  if (message) nextTick(() => codeInputRef.value?.select())
})

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  if (props.open) revealPanel()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <Transition name="lock-slide">
    <div v-if="open && container" ref="panelRef" class="tw-lock relative w-full max-w-2xl shrink-0" aria-live="polite">
      <section class="tw-narration space-y-3">
        <div class="flex items-start justify-between gap-3">
          <span class="tw-narration-label gap-1.5">
            <Lock class="w-3 h-3" />
            {{ effectiveHeader }}
          </span>
          <button type="button" class="tw-lock-close" :disabled="busy" title="Close (Esc)" @click="close">
            <X class="w-4 h-4" />
          </button>
        </div>

        <h3 class="tw-lock-title">{{ effectiveTitle }}</h3>
        <p v-if="effectiveDescription" class="tw-lock-description">{{ effectiveDescription }}</p>

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
            class="tw-lock-input"
          />
          <button type="submit" class="tw-lock-action" :disabled="busy || !codeInput.trim()">
            <Unlock class="w-4 h-4" />
            <span>Unlock</span>
          </button>
        </form>

        <!-- ITEM REQUIREMENT -->
        <template v-else-if="requiredItemId">
          <div v-if="hasRequiredKey && matchingInventoryKey" class="tw-lock-item">
            <div class="tw-lock-item-thumb">
              <img
                v-if="matchingInventoryKey.image_url && showImage(matchingInventoryKey.image_url)"
                :src="getImageUrl(matchingInventoryKey.image_url)"
                class="w-full h-full object-cover object-top"
                @error="handleImageError(matchingInventoryKey.image_url)"
              />
              <i v-else :class="['ra text-lg', getItemIcon(matchingInventoryKey.item_type ?? undefined), getTypeColor(matchingInventoryKey.item_type ?? undefined)]"></i>
            </div>
            <div class="flex-1 min-w-0">
              <p class="tw-lock-item-name">{{ matchingInventoryKey.name || matchingInventoryKey.id }}</p>
              <p class="tw-lock-hint line-clamp-2">{{ matchingInventoryKey.description || 'A special item carried in your inventory.' }}</p>
            </div>
            <button type="button" class="tw-lock-action" :disabled="busy" @click="handleUseKey">
              <Key class="w-4 h-4" />
              <span>Use Item</span>
            </button>
          </div>
          <p v-else class="tw-lock-hint">
            This {{ entityNoun }} requires an item you do not possess ({{ formatIdToName(requiredItemId) }}).
          </p>
        </template>

        <!-- RULE/PUZZLE REQUIREMENT -->
        <p v-else-if="requiredRule && !unlockExpression" class="tw-lock-hint">
          This {{ entityNoun }} cannot be opened directly. You must satisfy a condition or solve a puzzle in the world first.
        </p>

        <!-- SCRIPT GUARD / DIRECT UNLOCK -->
        <div v-else class="flex items-center justify-between gap-3">
          <p class="tw-lock-hint">
            {{ unlockExpression ? `This ${entityNoun} is held by a mechanism or condition in the world.` : 'The way is currently barred. You can attempt to unlock or open it.' }}
          </p>
          <button type="button" class="tw-lock-action shrink-0" :disabled="busy" @click="handleUnlockDirect">
            <Unlock class="w-4 h-4" />
            <span>Attempt Unlock</span>
          </button>
        </div>

        <p v-if="errorMessage" class="tw-choice-error">{{ errorMessage }}</p>
      </section>
    </div>
  </Transition>
</template>

<style scoped>
.lock-slide-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.lock-slide-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.lock-slide-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.lock-slide-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
