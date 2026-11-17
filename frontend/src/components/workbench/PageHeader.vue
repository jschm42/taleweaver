<script setup lang="ts">
/** Page title, one line of description and at most one primary and two secondary actions. */
withDefaults(defineProps<{ title: string; description?: string }>(), { description: '' })
</script>

<template>
  <header class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
    <div class="min-w-0">
      <div class="flex flex-wrap items-center gap-2">
        <h1 class="wb-title">{{ title }}</h1>
        <slot name="badge" />
      </div>
      <p v-if="description || $slots.description" class="wb-body text-wb-muted mt-1 max-w-3xl">
        <slot name="description">{{ description }}</slot>
      </p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2 shrink-0">
      <slot name="actions" />
    </div>
  </header>
</template>
