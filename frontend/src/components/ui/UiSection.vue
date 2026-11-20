<script setup lang="ts">
import { ref, watch } from 'vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'

/**
 * A titled group of content on a page or inside a card. With `collapsible` the content sits
 * behind a disclosure (closed unless `defaultOpen` or `open`), e.g. for "Advanced" options.
 */
const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    collapsible?: boolean
    defaultOpen?: boolean
    /** Controlled open state (use with v-model:open); optional. */
    open?: boolean
  }>(),
  { description: '', collapsible: false, defaultOpen: false, open: undefined },
)

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const isOpen = ref(props.open ?? props.defaultOpen)

watch(
  () => props.open,
  (value) => {
    if (value !== undefined) {
      isOpen.value = value
    }
  },
)

function setOpen(value: boolean): void {
  isOpen.value = value
  emit('update:open', value)
}
</script>

<template>
  <section class="space-y-4">
    <UiDisclosure v-if="collapsible" :open="isOpen" :label="title" :hint="description" @update:open="setOpen">
      <div class="space-y-4">
        <slot />
      </div>
    </UiDisclosure>
    <template v-else>
      <header class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <h3 class="wb-subheading">{{ title }}</h3>
          <p v-if="description" class="wb-hint mt-0.5">{{ description }}</p>
        </div>
        <div v-if="$slots.actions" class="flex items-center gap-2 shrink-0">
          <slot name="actions" />
        </div>
      </header>
      <slot />
    </template>
  </section>
</template>
