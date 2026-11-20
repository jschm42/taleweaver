<script setup lang="ts">
import { ref, toRef, useId } from 'vue'
import { X } from 'lucide-vue-next'
import { useFocusTrap } from '@/components/ui/focusTrap'
import UiIconButton from '@/components/ui/UiIconButton.vue'

/**
 * Side panel from the right that keeps the page visible behind it (e.g. the World-Builder
 * AI panel). Not for entity editing: entities get a full detail page.
 */
const open = defineModel<boolean>('open', { default: false })

const props = withDefaults(
  defineProps<{ title: string; description?: string; width?: 'md' | 'lg'; persistent?: boolean }>(),
  { description: '', width: 'md', persistent: false },
)

const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement | null>(null)
const titleId = `drawer-${useId()}`

function requestClose(): void {
  if (props.persistent) {
    return
  }
  open.value = false
  emit('close')
}

useFocusTrap(panel, toRef(() => open.value), { onEscape: requestClose })
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-x-6"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="opacity-0 translate-x-6"
    >
      <div v-if="open" class="fixed inset-0 z-[150] flex justify-end font-wb">
        <div class="absolute inset-0 bg-black/40" aria-hidden="true" @click="requestClose" />
        <aside
          ref="panel"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
          :class="[
            'relative h-full w-full flex flex-col bg-wb-overlay border-l border-wb-line-strong shadow-wb-float focus:outline-none',
            width === 'lg' ? 'sm:max-w-[720px]' : 'sm:max-w-[560px]',
          ]"
        >
          <header class="flex items-start justify-between gap-4 px-5 py-4 border-b border-wb-line">
            <div class="min-w-0">
              <h2 :id="titleId" class="wb-heading">{{ title }}</h2>
              <p v-if="description" class="wb-hint mt-1">{{ description }}</p>
            </div>
            <UiIconButton v-if="!persistent" :icon="X" label="Close" size="sm" @click="requestClose" />
          </header>
          <div class="flex-1 overflow-y-auto px-5 py-4 wb-body text-wb-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="flex items-center justify-end gap-2 px-5 py-3 border-t border-wb-line">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>
