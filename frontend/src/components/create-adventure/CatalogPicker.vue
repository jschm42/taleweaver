<script setup lang="ts">
/** Shows the chosen image style or tone as a 2:3 tile; "Change" opens the catalog dialog. */
import { computed, ref, type Component } from 'vue'
import type { CatalogTile } from '@/types'
import CatalogPickerDialog from '@/components/create-adventure/CatalogPickerDialog.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiInfoPopover from '@/components/ui/UiInfoPopover.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

const props = defineProps<{
  title: string
  help: string
  items: CatalogTile[]
  icon: Component
  loading?: boolean
}>()
const selectedId = defineModel<string>({ required: true })

const isOpen = ref(false)
const selected = computed(() => props.items.find((item) => item.id === selectedId.value) || null)
</script>

<template>
  <div class="flex gap-4">
    <button
      type="button"
      class="group relative aspect-[2/3] w-28 shrink-0 overflow-hidden rounded-xl border border-wb-line bg-wb-raised transition-colors hover:border-wb-line-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
      :aria-label="`Change ${title.toLowerCase()}`"
      :disabled="loading || !items.length"
      @click="isOpen = true"
    >
      <img
        v-if="selected?.image_url"
        :src="selected.image_url"
        :alt="selected.name"
        class="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
      />
      <span v-else class="absolute inset-0 flex items-center justify-center text-wb-faint">
        <UiSpinner v-if="loading" size="sm" label="Loading" />
        <component :is="icon" v-else class="h-6 w-6" aria-hidden="true" />
      </span>
    </button>
    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <div class="flex items-center gap-1.5">
        <p class="wb-overline">{{ title }}</p>
        <UiInfoPopover :title="title" :text="help" />
      </div>
      <p class="wb-heading truncate">{{ selected?.name || (loading ? 'Loading…' : 'None chosen') }}</p>
      <p class="wb-hint line-clamp-3">{{ selected?.description }}</p>
      <div class="mt-auto pt-2">
        <UiButton size="sm" :disabled="loading || !items.length" @click="isOpen = true">Change</UiButton>
      </div>
    </div>
    <CatalogPickerDialog
      v-model:open="isOpen"
      :title="title"
      :items="items"
      :selected-id="selectedId"
      :icon="icon"
      @select="(id) => (selectedId = id)"
    />
  </div>
</template>
