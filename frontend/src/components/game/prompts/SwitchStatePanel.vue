<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Check, ChevronRight } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'
import { parseMetadata, isTypingTarget } from './promptUtils'

/** State picker for a switch, shown inline at the end of the story feed. */
const props = defineProps<{
  open: boolean
  switchEntity: any
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  selectState: [targetState: string]
}>()

const switchConfig = computed(() => {
  const meta = parseMetadata(props.switchEntity?.metadata_json)
  return (meta.switch && typeof meta.switch === 'object') ? meta.switch : {}
})

const allStates = computed<string[]>(() => {
  const raw = switchConfig.value.states
  return Array.isArray(raw) ? raw.map((s: any) => String(s || '').trim()).filter(Boolean) : []
})

const currentState = computed(() => {
  return String(
    props.switchEntity?.switch_state ||
    switchConfig.value.initial_state ||
    (allStates.value[0] ?? '')
  ).trim().toUpperCase()
})

const imageUrl = computed(() => getImageUrl(props.switchEntity?.image_url) || null)

// Keyboard navigation (indexes over all states, starting at the active one)
const focusedIndex = ref(0)
const isCurrent = (state: string) => state.toUpperCase() === currentState.value

const select = (state: string) => {
  if (props.busy || isCurrent(state)) return
  emit('selectState', state.toUpperCase())
}

const onRevealed = () => {
  const idx = allStates.value.findIndex(isCurrent)
  focusedIndex.value = idx === -1 ? 0 : idx
}

const onKeyDown = (event: KeyboardEvent) => {
  const states = allStates.value
  if (!props.open || props.busy || !states.length || isTypingTarget(event.target)) return

  const handled = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Enter', ' ']
  if (!handled.includes(event.key)) return

  event.preventDefault()
  event.stopPropagation()

  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    focusedIndex.value = (focusedIndex.value + 1) % states.length
    return
  }
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    focusedIndex.value = (focusedIndex.value - 1 + states.length) % states.length
    return
  }
  select(states[focusedIndex.value])
}

onMounted(() => window.addEventListener('keydown', onKeyDown, { capture: true }))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown, { capture: true }))
</script>

<template>
  <InlinePromptPanel
    :open="open && !!switchEntity"
    label="Switch"
    :title="switchEntity?.name || 'Switch'"
    :description="switchEntity?.description || ''"
    :image-url="imageUrl"
    :busy="busy"
    :reveal-key="String(switchEntity?.id || '')"
    @close="emit('close')"
    @revealed="onRevealed"
  >
    <template #label-icon><i class="ra ra-lever"></i></template>

    <div class="grid gap-2" :class="allStates.length > 3 ? 'sm:grid-cols-2' : 'grid-cols-1'">
      <button
        v-for="(state, idx) in allStates"
        :key="state"
        type="button"
        :disabled="busy || isCurrent(state)"
        class="tw-choice-option"
        :class="{ 'is-focused': focusedIndex === idx && !isCurrent(state), 'is-current': isCurrent(state) }"
        @click="select(state)"
        @mouseenter="focusedIndex = idx"
      >
        <span class="tw-choice-number">
          <Check v-if="isCurrent(state)" class="w-3 h-3" stroke-width="3" />
          <ChevronRight v-else class="w-3 h-3" stroke-width="3" />
        </span>
        <span class="flex-1 font-mono tracking-wider">{{ state.toUpperCase() }}</span>
        <i v-if="busy && focusedIndex === idx && !isCurrent(state)" class="ra ra-hourglass text-xs animate-spin opacity-60"></i>
      </button>
    </div>

    <p class="tw-choice-hint">
      Use <kbd>↑ ↓</kbd> to navigate, <kbd>Enter</kbd> to confirm, <kbd>Esc</kbd> to close
    </p>
  </InlinePromptPanel>
</template>
