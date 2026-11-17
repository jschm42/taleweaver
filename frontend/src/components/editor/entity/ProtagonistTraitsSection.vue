<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import TraitFields from '@/components/editor/entity/TraitFields.vue'

const ef = useEntityFormContext()
</script>

<template>
  <TraitFields
    v-if="ef.type === 'protagonist'"
    goal-label="Motivation"
    goal-placeholder="What drives the protagonist? e.g. seeks revenge for the family's death"
    character-label="Personality"
    character-placeholder="How does the protagonist behave? e.g. sarcastic but loyal, prone to rash decisions"
  />
</template>
