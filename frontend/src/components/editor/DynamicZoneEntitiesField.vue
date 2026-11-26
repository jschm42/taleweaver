<script setup lang="ts">
/**
 * Author-placed entities of a dynamic zone (`dynamic_zone.required_entities`): Blueprint
 * [NPC] / [Item] blocks that every cluster of this zone contains exactly once, in the room of
 * their `depth:` (a number or `max`; without depth the first room). Unlike the generation
 * instructions they are guaranteed, also beyond the NPC and object caps.
 * Engine: backend/engine/world/dynamic_required_entities.py.
 */
import UiField from '@/components/ui/UiField.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const model = defineModel<string | null | undefined>({ default: '' })

const PLACEHOLDER = '[NPC: FOREMAN] Ghost Foreman\ndepth: max\ntype: BEING\nA pale shade who still counts the carts.\n\n[Item: MINE_KEY] Rusty Lift Key\ndepth: 2'
</script>

<template>
  <UiField
    label="Placed NPCs & items"
    hint="Blueprint blocks that always appear once per cluster; depth: 1-10 or max picks the room."
    info="In the Story Idea you write them as normal [NPC] or [Item] blocks with in: ZONE_ID; they land here. Without depth they appear in the first room generated."
  >
    <UiTextarea
      :model-value="model || ''"
      :rows="4"
      class="font-mono"
      :placeholder="PLACEHOLDER"
      @update:model-value="model = String($event ?? '').trim() ? String($event) : null"
    />
  </UiField>
</template>
