<script setup lang="ts">
import FormTextField from '@/components/editor/overview/FormTextField.vue'
import UiCard from '@/components/ui/UiCard.vue'

/** The hidden plot, the world's special rules and the opening text. */
</script>

<template>
  <UiCard title="Story" description="Only the Game Master sees the plot and rules; players see the intro once at the start.">
    <div class="space-y-6">
      <FormTextField
        field="plot"
        label="Plot"
        hint="Main plotline, hidden goals and core narrative. Reference entities with ##ID."
        placeholder="The main plotline, hidden goals, and core narrative..."
        :rows="8"
        generatable
      />
      <FormTextField
        field="rules"
        label="World rules"
        hint="Special rules the Game Master enforces in this world."
        placeholder="Special rules for this world..."
        :rows="5"
        generatable
      />
      <FormTextField
        field="intro_text"
        label="Intro text"
        hint="Shown once when a session starts."
        placeholder="The opening scene players read before their first move..."
        :rows="6"
        generatable
      />
    </div>
  </UiCard>
</template>
