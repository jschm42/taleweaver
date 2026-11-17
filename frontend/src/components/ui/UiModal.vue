<script setup lang="ts">
import { computed, ref, toRef, useId } from 'vue'
import { X } from 'lucide-vue-next'
import { useFocusTrap } from '@/components/ui/focusTrap'
import UiIconButton from '@/components/ui/UiIconButton.vue'

/**
 * Dialog for short tasks and questions. Teleported to <body>, traps focus, closes on Esc
 * and (unless `persistent`) on a backdrop click. For entity editing use a full page.
 */
const open = defineModel<boolean>('open', { default: false })

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    size?: 'sm' | 'md' | 'lg'
    /** No close on Esc, backdrop or X (e.g. while saving). */
    persistent?: boolean
    /** Use alertdialog semantics (questions that need an answer). */
    alert?: boolean
  }>(),
  { description: '', size: 'md', persistent: false, alert: false },
)

const emit = defineEmits<{ close: [] }>()

const panel = ref<HTMLElement | null>(null)
const titleId = `modal-${useId()}`
const descriptionId = `${titleId}-description`

const SIZE_CLASS = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-3xl' }
const panelClass = computed(() => SIZE_CLASS[props.size])

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
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      leave-active-class="transition duration-100 ease-in"
      leave-to-class="opacity-0"
    >
      <div v-if="open" class="fixed inset-0 z-[200] flex items-center justify-center p-4 font-wb">
        <div class="absolute inset-0 bg-black/60" aria-hidden="true" @click="requestClose" />
        <div
          ref="panel"
          :role="alert ? 'alertdialog' : 'dialog'"
          aria-modal="true"
          :aria-labelledby="titleId"
          :aria-describedby="description ? descriptionId : undefined"
          tabindex="-1"
          :class="[
            'relative w-full max-h-[calc(100vh-2rem)] flex flex-col rounded-xl bg-wb-overlay border border-wb-line-strong shadow-wb-float focus:outline-none',
            panelClass,
          ]"
        >
          <header class="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
            <div class="min-w-0">
              <h2 :id="titleId" class="wb-heading">{{ title }}</h2>
              <p v-if="description" :id="descriptionId" class="wb-hint mt-1">{{ description }}</p>
            </div>
            <UiIconButton v-if="!persistent" :icon="X" label="Close" size="sm" class="-mr-1 -mt-1" @click="requestClose" />
          </header>
          <div class="px-5 pb-5 overflow-y-auto wb-body text-wb-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="flex items-center justify-end gap-2 px-5 py-3 border-t border-wb-line">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
