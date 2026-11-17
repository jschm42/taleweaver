<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import NpcCombatSettings from '@/components/editor/NpcCombatSettings.vue'

const ef = useEntityFormContext()
</script>

<template>
  <div class="space-y-2">
    <p class="text-xs font-black text-slate-500 uppercase tracking-widest">Combat</p>
    <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
      How this NPC fights: damage, aggression, combat group, attributes, main attack and special attacks. Party settings are on the Companion tab.
      The damage switch is saved with Apply Changes; the sections below have their own Save buttons.
    </p>
  </div>

  <div class="p-4 bg-black/30 border border-white/10 rounded-2xl">
    <div class="flex items-center justify-between">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-slate-200 uppercase tracking-widest">NPC Can Be Damaged</p>
        <p class="text-[10px] text-slate-500 uppercase tracking-tighter">If disabled, the NPC never loses HP (scripts, Game Master, combat) and cannot be fought.</p>
      </div>
      <button
        type="button"
        @click="ef.localForm.is_killable = !ef.localForm.is_killable"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', ef.localForm.is_killable ? 'bg-emerald-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.is_killable ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>
  </div>

  <!-- NPC combat behaviour & special attacks (shared with the NPC combat modal) -->
  <div class="p-4 bg-black/30 border border-white/10 rounded-2xl">
    <NpcCombatSettings
      v-if="ef.props.adventureId && ef.props.npcData && !ef.props.isCreateEntityMode"
      :adventure-id="ef.props.adventureId"
      :npc="ef.props.npcData"
      :reference-options="ef.props.referenceOptions"
      @saved="ef.emit('combat-saved')"
    />
    <p v-else class="text-[11px] text-slate-400">Save the NPC first to configure attack behaviour, combat group and special attacks.</p>
  </div>
</template>
