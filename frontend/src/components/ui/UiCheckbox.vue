<script setup lang="ts">
import { useId } from 'vue'
import { Check } from 'lucide-vue-next'

const model = defineModel<boolean>({ default: false })

withDefaults(defineProps<{ label: string; description?: string; disabled?: boolean }>(), {
  description: '',
  disabled: false,
})

const inputId = `checkbox-${useId()}`
</script>

<template>
  <label :for="inputId" :class="['flex items-start gap-2.5 cursor-pointer', disabled ? 'opacity-50 cursor-not-allowed' : '']">
    <span class="relative mt-0.5 inline-flex h-4 w-4 shrink-0">
      <input
        :id="inputId"
        v-model="model"
        type="checkbox"
        :disabled="disabled"
        class="peer absolute inset-0 h-4 w-4 cursor-pointer appearance-none rounded-md border border-wb-line-strong bg-wb-raised checked:border-wb-accent checked:bg-wb-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent/50"
      />
      <Check class="pointer-events-none relative h-4 w-4 p-0.5 text-white opacity-0 peer-checked:opacity-100" aria-hidden="true" />
    </span>
    <span class="min-w-0">
      <span class="wb-label block !text-wb-strong">{{ label }}</span>
      <span v-if="description" class="wb-hint block">{{ description }}</span>
    </span>
  </label>
</template>
