<script setup lang="ts">
import { Plus, Trash2 } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiSection from '@/components/ui/UiSection.vue'

const ef = useEntityFormContext()

function removeItem(index: number): void {
  ef.localForm.inventory_input = ef.localForm.inventory_input.filter((_: string, i: number) => i !== index)
}

function addItem(): void {
  ef.localForm.inventory_input = [...(ef.localForm.inventory_input || []), '']
}
</script>

<template>
  <UiSection
    v-if="ef.type === 'npc'"
    title="Inventory"
    description="Items the character carries; dropped as loot when defeated."
  >
    <div class="space-y-2">
      <div v-for="(_item, idx) in ef.localForm.inventory_input" :key="idx" class="flex items-center gap-2">
        <EntityReferenceCombobox
          v-model="ef.localForm.inventory_input[idx]"
          :options="ef.itemReferenceOptions"
          placeholder="Select an item"
          :enable-search="true"
        />
        <UiIconButton :icon="Trash2" label="Remove item" variant="danger" size="sm" @click="removeItem(idx)" />
      </div>
      <p v-if="!ef.localForm.inventory_input || ef.localForm.inventory_input.length === 0" class="wb-hint">
        Nothing carried; the character drops nothing when defeated.
      </p>
      <UiButton size="sm" :icon="Plus" @click="addItem">Add item</UiButton>
    </div>
  </UiSection>
</template>
