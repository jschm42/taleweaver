<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import NpcCompanionSettings from '@/components/editor/NpcCompanionSettings.vue'
import RecruitTriggerFields from '@/components/editor/RecruitTriggerFields.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSection from '@/components/ui/UiSection.vue'

const ef = useEntityFormContext()
</script>

<template>
  <div class="space-y-6">
    <p class="wb-body text-wb-muted">
      Whether this character can join the party, how the player recruits it, and what is narrated when recruiting
      succeeds or fails.
    </p>

    <template v-if="ef.props.adventureId && ef.props.npcData && !ef.props.isCreateEntityMode">
      <UiNotice>Companion settings are saved with their own button; the recruit triggers below are saved with the form.</UiNotice>
      <NpcCompanionSettings :adventure-id="ef.props.adventureId" :npc="ef.props.npcData" @saved="ef.emit('combat-saved')" />
    </template>
    <UiNotice v-else>Save the character first to make it a companion.</UiNotice>

    <UiSection title="Recruit triggers" description="Saved with the form." class="border-t border-wb-line pt-6">
      <RecruitTriggerFields
        v-model:success-script="ef.localForm.on_recruit_success_script"
        v-model:success-text="ef.localForm.on_recruit_success_text"
        v-model:failure-script="ef.localForm.on_recruit_failure_script"
        v-model:failure-text="ef.localForm.on_recruit_failure_text"
      />
    </UiSection>
  </div>
</template>
