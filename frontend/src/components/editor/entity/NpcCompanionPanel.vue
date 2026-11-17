<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import RecruitTriggerFields from '@/components/editor/RecruitTriggerFields.vue'
import NpcCompanionSettings from '@/components/editor/NpcCompanionSettings.vue'

const ef = useEntityFormContext()
</script>

<template>
  <div class="space-y-2">
    <p class="text-xs font-black text-slate-500 uppercase tracking-widest">Companion</p>
    <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
      Whether this NPC can join the party, how the player recruits it, and what is narrated when recruiting succeeds or fails.
      The companion settings have their own Save button; the recruit triggers are saved with Apply Changes.
    </p>
  </div>

  <!-- Companion (sidekick) settings -->
  <div v-if="ef.props.adventureId && ef.props.npcData && !ef.props.isCreateEntityMode" class="p-4 bg-black/30 border border-white/10 rounded-2xl">
    <NpcCompanionSettings
      :adventure-id="ef.props.adventureId"
      :npc="ef.props.npcData"
      @saved="ef.emit('combat-saved')"
    />
  </div>
  <p v-else class="text-[11px] text-slate-400">Save the NPC first to make it a companion.</p>

  <RecruitTriggerFields
    v-model:success-script="ef.localForm.on_recruit_success_script"
    v-model:success-text="ef.localForm.on_recruit_success_text"
    v-model:failure-script="ef.localForm.on_recruit_failure_script"
    v-model:failure-text="ef.localForm.on_recruit_failure_text"
  />
</template>
