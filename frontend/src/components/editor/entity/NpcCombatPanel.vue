<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import NpcCombatSettings from '@/components/editor/NpcCombatSettings.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import type { NpcCombatProfileState } from '@/composables/editor/useNpcCombatProfile'

defineProps<{ profile: NpcCombatProfileState | null }>()

const ef = useEntityFormContext()
</script>

<template>
  <div class="space-y-6">
    <p class="wb-body text-wb-muted">
      How this character fights: damage, aggression, combat group, main attack and special attacks. Attributes and AC
      are on the Stats tab, party settings on the Companion tab.
    </p>

    <UiToggle
      v-model="ef.localForm.is_killable"
      label="Can be damaged"
      description="Off: never loses HP (scripts, Game Master, combat) and cannot be fought."
    />

    <div class="space-y-6 border-t border-wb-line pt-6">
      <template v-if="ef.props.adventureId && ef.props.npcData && !ef.props.isCreateEntityMode">
        <NpcCombatSettings
          :adventure-id="ef.props.adventureId"
          :npc="ef.props.npcData"
          :reference-options="ef.props.referenceOptions"
          :profile="profile"
          @saved="ef.emit('combat-saved')"
        />
      </template>
      <UiNotice v-else>Save the character first to set attack behaviour, combat group and special attacks.</UiNotice>
    </div>
  </div>
</template>
