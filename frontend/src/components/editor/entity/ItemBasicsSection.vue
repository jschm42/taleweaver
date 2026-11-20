<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const ef = useEntityFormContext()

const ITEM_TYPES = [
  { value: 'DEFAULT', label: 'Default' },
  { value: 'CONSUMABLE', label: 'Consumable' },
  { value: 'WEARABLE', label: 'Wearable' },
  { value: 'WEAPON', label: 'Weapon' },
  { value: 'CONSTRUCTABLE', label: 'Recipe (constructable)' },
  { value: 'READABLE', label: 'Readable' },
  { value: 'CONTAINER', label: 'Container' },
  { value: 'CONTAINER_SWITCH', label: 'Container with switch' },
  { value: 'SWITCH', label: 'Switch' },
]

const typeLabel = (type: unknown): string =>
  ITEM_TYPES.find((option) => option.value === String(type || '').toUpperCase())?.label ?? String(type || '')
</script>

<template>
  <div class="space-y-5">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <UiField label="Item type" :hint="ef.localForm.is_item_type_fixed ? 'Fixed for this item.' : ''">
        <UiSelect v-if="!ef.localForm.is_item_type_fixed" v-model="ef.localForm.item_type" :options="ITEM_TYPES" />
        <UiInput v-else :model-value="typeLabel(ef.localForm.item_type)" disabled />
      </UiField>
      <!-- Recipes are never picked up: no portable switch. -->
      <div v-if="!ef.isRecipe" class="flex items-end">
        <UiToggle
          v-if="ef.currentItemType !== 'WEARABLE'"
          v-model="ef.localForm.is_portable"
          label="Portable"
          description="The player can pick it up."
          class="w-full"
        />
        <p v-else class="wb-hint pb-2">Wearables are always portable.</p>
      </div>
    </div>

    <UiToggle
      v-if="!['CONTAINER', 'CONTAINER_SWITCH', 'SWITCH', 'CONSTRUCTABLE'].includes(ef.currentItemType)"
      v-model="ef.localForm.locked"
      label="Locked (cannot be taken)"
      description="Visible and inspectable, but cannot be picked up until a script unlocks it: tw.objects.unlock('ID')."
    />

    <UiToggle
      v-if="ef.currentItemType !== 'CONSTRUCTABLE'"
      v-model="ef.localForm.quest_item"
      label="Quest item"
      description="The player can never give it away and the Game Master cannot take it; scripts still can (tw.player.transfer_item). Shown with a gold frame in the game."
    />
  </div>
</template>
