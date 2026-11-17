<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Backpack, Hammer, Plus, Trash2 } from 'lucide-vue-next'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import { itemRefId, type CreateItemTarget, type ProtagonistData, type ReferenceOption } from './protagonistTypes'

/** Items the protagonist carries at the start. The list saves on every change. */
const props = defineProps<{ protagonist: ProtagonistData; referenceOptions: ReferenceOption[] }>()
const emit = defineEmits<{
  'save-field': [field: string, value: string[]]
  'create-new-item': [target: CreateItemTarget]
}>()

const items = ref<string[]>([])

watch(
  () => props.protagonist.inventory,
  (inventory) => {
    items.value = (inventory || []).map(itemRefId)
  },
  { immediate: true },
)

const objectOptions = computed(() => props.referenceOptions.filter((opt) => opt.type === 'OBJECT'))

function save(): void {
  emit('save-field', 'inventory', items.value.filter((id) => id !== ''))
}

function updateItem(index: number, itemId: string): void {
  items.value[index] = itemId
  save()
}

function removeItem(index: number): void {
  items.value.splice(index, 1)
  save()
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="wb-hint">Items in the backpack at the start. Changes are saved at once.</p>
      <div class="flex gap-2">
        <UiButton size="sm" :icon="Plus" @click="items.push('')">Select item</UiButton>
        <UiButton size="sm" :icon="Hammer" @click="emit('create-new-item', { type: 'inventory' })">Create new</UiButton>
      </div>
    </div>

    <UiEmptyState
      v-if="items.length === 0"
      :icon="Backpack"
      title="The backpack is empty"
      description="Select an existing item or create a new one."
    />

    <ul v-else class="space-y-2">
      <li v-for="(itemId, index) in items" :key="index" class="flex items-center gap-2">
        <span class="wb-hint w-6 shrink-0 tabular-nums">{{ index + 1 }}</span>
        <div class="min-w-0 flex-grow">
          <EntityReferenceCombobox
            :model-value="itemId"
            :options="objectOptions"
            placeholder="Select an item"
            :enable-search="true"
            @update:model-value="updateItem(index, $event)"
          />
        </div>
        <UiIconButton
          :icon="Hammer"
          label="Create a new item for this entry"
          size="sm"
          @click="emit('create-new-item', { type: 'inventory', index })"
        />
        <UiIconButton :icon="Trash2" label="Remove from inventory" variant="danger" size="sm" @click="removeItem(index)" />
      </li>
    </ul>
  </div>
</template>
