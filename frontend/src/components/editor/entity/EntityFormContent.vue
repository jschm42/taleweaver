<script setup lang="ts">
import { computed } from 'vue'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityImagePreview from '@/components/editor/EntityImagePreview.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import EntityIdField from './EntityIdField.vue'
import EntityStatsSection from './EntityStatsSection.vue'
import ProtagonistTraitsSection from './ProtagonistTraitsSection.vue'
import NpcProfileSection from './NpcProfileSection.vue'
import NpcMovementSection from './NpcMovementSection.vue'
import NpcNotesSection from './NpcNotesSection.vue'
import NpcInventorySection from './NpcInventorySection.vue'
import NpcVisibilitySection from './NpcVisibilitySection.vue'
import ItemBasicsSection from './ItemBasicsSection.vue'
import ItemVisibilitySection from './ItemVisibilitySection.vue'
import ItemEquipmentSection from './ItemEquipmentSection.vue'
import ItemConsumableSection from './ItemConsumableSection.vue'
import ItemRecipeSection from './ItemRecipeSection.vue'
import ItemSwitchSection from './ItemSwitchSection.vue'
import ItemContainerSection from './ItemContainerSection.vue'
import ItemReadableSection from './ItemReadableSection.vue'
import EntityDescriptionSection from './EntityDescriptionSection.vue'
import NpcCombatPanel from './NpcCombatPanel.vue'
import NpcCompanionPanel from './NpcCompanionPanel.vue'
import ItemTriggersPanel from './ItemTriggersPanel.vue'
import SceneTriggersPanel from './SceneTriggersPanel.vue'
import NpcTriggersPanel from './NpcTriggersPanel.vue'
import NpcStatsPanel from './NpcStatsPanel.vue'
import { useNpcCombatProfile } from '@/composables/editor/useNpcCombatProfile'

/** Image row, tabs and tab panels of the entity form (shared by the modal and the detail page). */
const ef = useEntityFormContext()

// Attributes (Stats tab) and main attack (Combat tab) are saved together, so both tabs share one profile.
const savedNpc = computed(() => (ef.type === 'npc' && !ef.props.isCreateEntityMode ? (ef.props.npcData ?? null) : null))
const npcProfile = useNpcCombatProfile(() => ef.props.adventureId, () => savedNpc.value)
const profile = computed(() => (savedNpc.value && ef.props.adventureId ? npcProfile : null))

const NPC_TABS = [
  { id: 'stats' as const, label: 'Stats' },
  { id: 'movement' as const, label: 'Movement' },
  { id: 'inventory' as const, label: 'Inventory' },
  { id: 'combat' as const, label: 'Combat' },
  { id: 'companion' as const, label: 'Companion' },
]

const tabs = computed(() => [
  { id: 'simple' as const, label: 'General' },
  ...(ef.type === 'npc' ? NPC_TABS : []),
  { id: 'advanced' as const, label: ef.type === 'scene' ? 'Triggers' : 'Advanced' },
])
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <EntityImagePreview :image-url="ef.entityImageUrl" :label="ef.localForm.name || ef.entityId" />
      <div class="min-w-0">
        <p class="wb-subheading truncate">{{ ef.localForm.name || 'Unnamed' }}</p>
        <p class="wb-mono text-wb-muted">{{ ef.props.isCreateEntityMode ? 'new' : ef.entityId }}</p>
      </div>
    </div>

    <UiTabs v-model="ef.activeTab" :tabs="tabs" label="Form sections" />

    <div v-show="ef.activeTab === 'simple'" class="space-y-6">
      <EntityIdField />
      <EntityStatsSection />
      <ProtagonistTraitsSection />
      <NpcProfileSection />
      <NpcNotesSection />
      <NpcVisibilitySection />
      <div v-if="ef.type === 'object'" class="space-y-6">
        <ItemBasicsSection />
        <ItemVisibilitySection />
        <ItemEquipmentSection />
        <ItemConsumableSection />
        <ItemRecipeSection />
        <ItemSwitchSection />
        <ItemContainerSection />
        <ItemReadableSection />
      </div>
      <EntityDescriptionSection />
    </div>

    <div v-if="ef.type === 'npc'" v-show="ef.activeTab === 'stats'">
      <NpcStatsPanel :profile="profile" />
    </div>

    <div v-if="ef.type === 'npc'" v-show="ef.activeTab === 'movement'">
      <NpcMovementSection />
    </div>

    <div v-if="ef.type === 'npc'" v-show="ef.activeTab === 'inventory'">
      <NpcInventorySection />
    </div>

    <div v-if="ef.type === 'npc'" v-show="ef.activeTab === 'combat'">
      <NpcCombatPanel :profile="profile" />
    </div>

    <div v-if="ef.type === 'npc'" v-show="ef.activeTab === 'companion'">
      <NpcCompanionPanel />
    </div>

    <div v-show="ef.activeTab === 'advanced'" class="space-y-6">
      <p class="wb-body text-wb-muted">Scripts and narration cues that run on interaction. Leave empty when not needed.</p>
      <ItemTriggersPanel v-if="ef.type === 'object'" />
      <SceneTriggersPanel v-else-if="ef.type === 'scene'" />
      <NpcTriggersPanel v-else-if="ef.type === 'npc'" />
    </div>
  </div>
</template>
