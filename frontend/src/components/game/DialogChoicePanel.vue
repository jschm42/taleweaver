<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import type { PendingDialog } from '@/types'

/**
 * Choice dialog opened by an adventure script (tw.dialog.choose), shown inline at the end of
 * the story feed. It cannot be dismissed: the story only continues once the player picks one
 * of the options.
 */
const props = defineProps<{
  open: boolean
  dialog: PendingDialog | null
  busy?: boolean
  errorMessage?: string
}>()

const emit = defineEmits<{
  choose: [index: number]
}>()

const focusedIndex = ref(0)
const panelRef = ref<HTMLElement | null>(null)

const scrollIntoView = (): void => {
  nextTick(() => panelRef.value?.scrollIntoView({ block: 'end', behavior: 'smooth' }))
}

watch(() => props.dialog?.id, () => {
  focusedIndex.value = 0
  scrollIntoView()
})

watch(() => props.open, (isOpen) => {
  if (isOpen) scrollIntoView()
})

const choose = (index: number): void => {
  if (props.busy) return
  emit('choose', index)
}

const isTypingTarget = (target: EventTarget | null): boolean => {
  const element = target as HTMLElement | null
  return !!element && (element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName))
}

const onKeyDown = (event: KeyboardEvent): void => {
  const options = props.dialog?.options || []
  if (!props.open || !options.length || isTypingTarget(event.target)) return

  const handled = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Enter', ' ']
  const digit = Number.parseInt(event.key, 10)
  const isDigit = digit >= 1 && digit <= options.length
  if (!handled.includes(event.key) && !isDigit) return

  event.preventDefault()
  event.stopPropagation()

  if (isDigit) {
    choose(options[digit - 1].index)
    return
  }
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    focusedIndex.value = (focusedIndex.value + 1) % options.length
    return
  }
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    focusedIndex.value = (focusedIndex.value - 1 + options.length) % options.length
    return
  }
  choose(options[focusedIndex.value].index)
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown, { capture: true })
  if (props.open) scrollIntoView()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown, { capture: true }))
</script>

<template>
  <Transition name="dlg-slide">
    <div v-if="open && dialog" ref="panelRef" class="tw-choice relative w-full max-w-2xl shrink-0" aria-live="polite">
      <section class="tw-narration space-y-3">
        <span class="tw-narration-label">{{ dialog.speaker || 'Your choice' }}</span>

        <p class="tw-choice-prompt">{{ dialog.prompt || 'What do you do?' }}</p>

        <div class="space-y-2">
          <button
            v-for="(option, idx) in dialog.options"
            :key="option.index"
            type="button"
            :disabled="busy"
            class="tw-choice-option"
            :class="{ 'is-focused': focusedIndex === idx }"
            @click="choose(option.index)"
            @mouseenter="focusedIndex = idx"
          >
            <span class="tw-choice-number">{{ idx + 1 }}</span>
            <span class="flex-1">{{ option.label }}</span>
            <i v-if="busy && focusedIndex === idx" class="ra ra-hourglass text-xs animate-spin opacity-60"></i>
          </button>
        </div>

        <p v-if="errorMessage" class="tw-choice-error">{{ errorMessage }}</p>

        <p class="tw-choice-hint">
          Press <kbd>1</kbd>–<kbd>{{ dialog.options.length }}</kbd> or use <kbd>↑ ↓</kbd> and <kbd>Enter</kbd>
        </p>
      </section>
    </div>
  </Transition>
</template>

<style scoped>
.dlg-slide-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.dlg-slide-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dlg-slide-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.dlg-slide-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
