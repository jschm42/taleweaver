<script setup lang="ts">
/** A flat surface with an optional header. Never put a UiCard inside another UiCard. */
withDefaults(defineProps<{ title?: string; description?: string; padded?: boolean }>(), {
  title: '',
  description: '',
  padded: true,
})
</script>

<template>
  <section class="rounded-xl bg-wb-surface border border-wb-line">
    <header
      v-if="title || $slots.actions"
      class="flex items-start justify-between gap-4 px-5 pt-4 pb-3 border-b border-wb-line"
    >
      <div class="min-w-0">
        <h3 v-if="title" class="wb-heading">{{ title }}</h3>
        <p v-if="description" class="wb-hint mt-0.5">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="flex items-center gap-2 shrink-0">
        <slot name="actions" />
      </div>
    </header>
    <div :class="padded ? 'p-5' : ''">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="flex items-center justify-end gap-2 px-5 py-3 border-t border-wb-line">
      <slot name="footer" />
    </footer>
  </section>
</template>
