<script setup lang="ts">
import type { Component } from 'vue'

withDefaults(defineProps<{ title: string; description?: string; icon?: Component }>(), {
  description: '',
  icon: undefined,
})
</script>

<template>
  <div class="flex flex-col items-center justify-center text-center gap-3 rounded-xl border border-dashed border-wb-line-strong px-6 py-10">
    <component :is="icon" v-if="icon" class="w-8 h-8 text-wb-faint" aria-hidden="true" />
    <div class="space-y-1 max-w-sm">
      <p class="wb-subheading">{{ title }}</p>
      <p v-if="description" class="wb-hint">{{ description }}</p>
    </div>
    <div v-if="$slots.action" class="mt-1">
      <slot name="action" />
    </div>
  </div>
</template>
