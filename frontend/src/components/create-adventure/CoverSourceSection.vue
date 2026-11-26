<script setup lang="ts">
/** Cover mode: the adventure a new one is based on, how close it stays and what it may reuse. */
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiRange from '@/components/ui/UiRange.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

const { form, sourceAdventure, isLoadingCoverSource } = useCreateAdventureContext()
</script>

<template>
  <UiCard title="Based on" description="A new adventure inspired by an existing one: a sequel, spin-off or variation.">
    <div class="space-y-4">
      <div v-if="isLoadingCoverSource" class="flex items-center gap-2">
        <UiSpinner size="sm" label="Loading the source adventure" />
        <span class="wb-hint">Loading the source adventure…</span>
      </div>
      <div v-else class="flex gap-4">
        <img
          v-if="sourceAdventure?.image_url"
          :src="sourceAdventure.image_url"
          :alt="sourceAdventure.title"
          class="aspect-[2/3] w-20 shrink-0 rounded-xl border border-wb-line object-cover"
        />
        <div class="min-w-0">
          <p class="wb-heading">{{ sourceAdventure?.title || 'Unknown source' }}</p>
          <p class="wb-hint mt-1 line-clamp-4 whitespace-pre-wrap">
            {{ sourceAdventure?.teaser || sourceAdventure?.original_prompt || sourceAdventure?.plot || 'No description.' }}
          </p>
        </div>
      </div>
      <UiField label="Similarity" hint="0 % = freely inspired, 100 % = very close to the original.">
        <UiRange v-model="form.cover_similarity_percent" :min="0" :max="100" unit=" %" />
      </UiField>
      <UiCheckbox
        v-model="form.allow_reuse_source_assets"
        label="Reuse images of the original"
        description="Pictures that still fit the new story are taken over instead of generated."
      />
    </div>
  </UiCard>
</template>
