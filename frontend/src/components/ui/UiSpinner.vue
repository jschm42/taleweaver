<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'

withDefaults(defineProps<{ size?: 'sm' | 'md' | 'lg'; label?: string }>(), {
  size: 'md',
  label: 'Loading',
})

const SIZE_CLASS: Record<string, string> = { sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-8 h-8' }
</script>

<template>
  <span role="status" class="inline-flex items-center text-wb-muted">
    <Loader2 :class="['animate-spin', SIZE_CLASS[size]]" aria-hidden="true" />
    <span class="sr-only">{{ label }}</span>
  </span>
</template>
