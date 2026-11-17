<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const ef = useEntityFormContext()

const isContainer = computed(() => ['CONTAINER', 'CONTAINER_SWITCH'].includes(ef.currentItemType))
const capacityError = computed(() => {
  const min = Number(ef.localForm.min_items || 0)
  const max = Number(ef.localForm.max_items || 0)
  return min > 0 && max > 0 && min > max ? 'The minimum cannot be greater than the capacity.' : null
})
const hasTriggers = computed(
  () =>
    ef.localForm.on_unlock_success_script ||
    ef.localForm.on_unlock_failure_script ||
    ef.localForm.on_items_added_script ||
    ef.localForm.on_items_removed_script,
)

function removeItem(index: number): void {
  ef.localForm.inventory_input = ef.localForm.inventory_input.filter((_: string, i: number) => i !== index)
}

function addItem(): void {
  ef.localForm.inventory_input = [...(ef.localForm.inventory_input || []), '']
}
</script>

<template>
  <UiSection v-if="isContainer" title="Container" class="border-t border-wb-line pt-6">
    <UiToggle v-model="ef.localForm.locked" label="Locked" description="Opens with a code or a key item." />
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <UiField label="Unlock code">
        <UiInput v-model="ef.localForm.code_to_unlock" maxlength="20" placeholder="ALPHA or 4711" class="wb-mono" />
      </UiField>
      <UiField label="Key item">
        <EntityReferenceCombobox
          v-model="ef.localForm.item_to_unlock"
          :options="ef.keyItemReferenceOptions"
          placeholder="Select an item"
          :enable-search="true"
        />
      </UiField>
    </div>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <UiField label="Minimum items" hint="Needed inside, e.g. 3 for a fuse box with three parts. 0 = none.">
        <UiInput v-model="ef.localForm.min_items" type="number" min="0" max="50" placeholder="0" />
      </UiField>
      <UiField label="Capacity" hint="Fits inside, e.g. 1 for a coin slot. 0 = unlimited." :error="capacityError">
        <UiInput v-model="ef.localForm.max_items" type="number" min="0" max="50" placeholder="0" />
      </UiField>
    </div>

    <UiField label="Contents" hint="Items inside this container.">
      <div class="space-y-2">
        <div v-for="(_item, idx) in ef.localForm.inventory_input" :key="idx" class="flex items-center gap-2">
          <EntityReferenceCombobox
            v-model="ef.localForm.inventory_input[idx]"
            :options="ef.containedItemReferenceOptions"
            placeholder="Select an item"
            :enable-search="true"
          />
          <UiIconButton :icon="Trash2" label="Remove item" variant="danger" size="sm" @click="removeItem(idx)" />
        </div>
        <UiButton size="sm" :icon="Plus" @click="addItem">Add item</UiButton>
      </div>
    </UiField>

    <!-- Contents are created only when opened: the script editor measures itself on creation. -->
    <UiDisclosure
      v-model:open="ef.showContainerGuard"
      label="Unlock guard"
      :hint="ef.localForm.unlock_expression ? 'configured' : 'optional'"
    >
      <ScriptEditor
        v-if="ef.showContainerGuard"
        v-model="ef.localForm.unlock_expression"
        label="Guard expression"
        help-text="Python boolean expression checked when unlocking. If false, unlocking fails."
        context="guard_expression"
        placeholder="e.g. tw.vars.get('has_badge') == True or tw.switches.get('CHEST_LOCK') == 'OPEN'"
        min-height="90px"
      />
    </UiDisclosure>

    <UiDisclosure v-model:open="ef.showContainerTriggers" label="Container triggers" :hint="hasTriggers ? 'configured' : 'optional'">
      <div v-if="ef.showContainerTriggers" class="space-y-6">
        <TriggerScriptField
          v-model:script="ef.localForm.on_unlock_success_script"
          v-model:text="ef.localForm.on_unlock_success_text"
          label="On unlock success"
          help="Runs when the container is unlocked."
          context="container_unlock_success"
          text-placeholder="e.g. The heavy chest lid springs open with a satisfying clack."
        />
        <TriggerScriptField
          v-model:script="ef.localForm.on_unlock_failure_script"
          v-model:text="ef.localForm.on_unlock_failure_text"
          label="On unlock failure"
          help="Runs when unlocking fails or the guard blocks it."
          context="container_unlock_failure"
          text-placeholder="e.g. A small jolt zaps your fingers! The container remains shut."
        />
        <TriggerScriptField
          v-model:script="ef.localForm.on_items_added_script"
          v-model:text="ef.localForm.on_items_added_text"
          label="On items added"
          help="Runs once after the player put items in. added_items and added_item_ids are available."
          context="container_items_added"
          text-placeholder="e.g. The offering bowl glows faintly as the items settle inside."
        />
        <TriggerScriptField
          v-model:script="ef.localForm.on_items_removed_script"
          v-model:text="ef.localForm.on_items_removed_text"
          label="On items removed"
          help="Runs once after the player took items out. removed_items and removed_item_ids are available."
          context="container_items_removed"
          text-placeholder="e.g. The chamber resets as you take the item out."
        />
      </div>
    </UiDisclosure>
  </UiSection>
</template>
