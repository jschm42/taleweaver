<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { X } from 'lucide-vue-next'
import { formatEntityRefs } from '@/utils/entityRefs'

/**
 * Shell for prompts answered inline at the end of the story feed (locks, switches, readables),
 * like DialogChoicePanel. The box is a .tw-narration, so it takes the active dialog skin.
 * Esc or the close button dismisses it.
 */
const props = withDefaults(defineProps<{
  open: boolean
  label: string
  title: string
  description?: string
  imageUrl?: string | null
  busy?: boolean
  /** Changes when the open panel switches to another entity, which scrolls it into view again. */
  revealKey?: string
  /** Long content (readables) is scrolled to its start instead of its end. */
  scrollBlock?: ScrollLogicalPosition
}>(), {
  description: '',
  imageUrl: null,
  revealKey: '',
  scrollBlock: 'end',
})

const emit = defineEmits<{
  close: []
  /** Fired after the panel opened and scrolled into view (e.g. to focus an input). */
  revealed: []
}>()

const panelRef = ref<HTMLElement | null>(null)
const imageFailed = ref(false)

const close = () => {
  if (props.busy) return
  emit('close')
}

const reveal = () => {
  nextTick(() => {
    panelRef.value?.scrollIntoView({ block: props.scrollBlock, behavior: 'smooth' })
    emit('revealed')
  })
}

const onKeyDown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape' || !props.open) return
  close()
}

watch(() => [props.open, props.revealKey], () => {
  if (props.open) reveal()
})

watch(() => props.imageUrl, () => {
  imageFailed.value = false
})

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  if (props.open) reveal()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <Transition name="prompt-slide">
    <div v-if="open" ref="panelRef" class="tw-prompt relative w-full max-w-2xl shrink-0" aria-live="polite">
      <section class="tw-narration space-y-3">
        <div class="flex items-start justify-between gap-3">
          <span class="tw-narration-label gap-1.5">
            <slot name="label-icon" />
            {{ label }}
          </span>
          <button type="button" class="tw-prompt-close" :disabled="busy" title="Close (Esc)" @click="close">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="flex items-start gap-4">
          <div v-if="imageUrl && !imageFailed" class="tw-prompt-portrait">
            <img :src="imageUrl" :alt="title" class="w-full h-full object-cover object-top" @error="imageFailed = true" />
          </div>
          <div class="flex-1 min-w-0 space-y-2">
            <h3 class="tw-prompt-title">{{ title }}</h3>
            <p v-if="description" class="tw-prompt-description" v-html="formatEntityRefs(description)"></p>
            <slot name="aside" />
          </div>
        </div>

        <slot />
      </section>
    </div>
  </Transition>
</template>

<style scoped>
.prompt-slide-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.prompt-slide-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.prompt-slide-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.prompt-slide-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
