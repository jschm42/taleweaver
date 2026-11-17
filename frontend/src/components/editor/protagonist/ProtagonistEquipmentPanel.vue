<script setup lang="ts">
import { computed } from 'vue'
import { Hammer } from 'lucide-vue-next'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import { itemRefId, type CreateItemTarget, type ProtagonistData, type ReferenceOption } from './protagonistTypes'

/** Items the protagonist wears at the start, one per slot. A slot saves when it changes. */
const props = defineProps<{ protagonist: ProtagonistData; referenceOptions: ReferenceOption[] }>()
const emit = defineEmits<{
  'save-field': [field: string, value: Record<string, string | null>]
  'create-new-item': [target: CreateItemTarget]
}>()

const SLOTS = [
  { key: 'Head', label: 'Head' },
  { key: 'Neck', label: 'Necklace / amulet' },
  { key: 'Chest', label: 'Armor / chest' },
  { key: 'Arms', label: 'Bracers / arms' },
  { key: 'Hands', label: 'Gloves / hands' },
  { key: 'Legs', label: 'Greaves / legs' },
  { key: 'Feet', label: 'Boots / feet' },
  { key: 'Ring_1', label: 'Left ring' },
  { key: 'Ring_2', label: 'Right ring' },
  { key: 'MainHand', label: 'Main hand weapon' },
  { key: 'OffHand', label: 'Off hand shield / weapon' },
]

const objectOptions = computed(() => props.referenceOptions.filter((opt) => opt.type === 'OBJECT'))

function slotItemId(slotKey: string): string {
  return itemRefId(props.protagonist.equipment?.[slotKey])
}

function saveSlot(slotKey: string, itemId: string): void {
  const equipment: Record<string, string | null> = {}
  for (const [key, value] of Object.entries(props.protagonist.equipment || {})) {
    equipment[key] = itemRefId(value) || null
  }
  equipment[slotKey] = itemId || null
  emit('save-field', 'equipment', equipment)
}
</script>

<template>
  <div class="space-y-4">
    <p class="wb-hint">Items the protagonist starts with equipped. Each slot is saved as soon as it changes.</p>
    <div class="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-2">
      <UiField v-for="slot in SLOTS" :key="slot.key" :label="slot.label">
        <div class="flex items-center gap-2">
          <div class="min-w-0 flex-grow">
            <EntityReferenceCombobox
              :model-value="slotItemId(slot.key)"
              :options="objectOptions"
              placeholder="Empty slot"
              @update:model-value="saveSlot(slot.key, $event)"
            />
          </div>
          <UiIconButton
            :icon="Hammer"
            label="Create a new item for this slot"
            size="sm"
            @click="emit('create-new-item', { type: 'equipment', key: slot.key })"
          />
        </div>
      </UiField>
    </div>
  </div>
</template>
