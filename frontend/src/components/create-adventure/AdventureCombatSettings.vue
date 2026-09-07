<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, Shield, ShieldOff } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

type RuleMode = 'rpg' | 'story' | 'chat'

const props = defineProps<{
  ruleEnforcementMode: RuleMode
  canDamageNpcs: boolean
  npcsCanDamageProtagonist: boolean
}>()

const emit = defineEmits<{
  (e: 'update:canDamageNpcs', value: boolean): void
  (e: 'update:npcsCanDamageProtagonist', value: boolean): void
}>()

const isRpgMode = computed(() => props.ruleEnforcementMode === 'rpg')

function toggleCanDamageNpcs() {
  if (!isRpgMode.value) return
  emit('update:canDamageNpcs', !props.canDamageNpcs)
}

function toggleNpcsCanDamageProtagonist() {
  if (!isRpgMode.value) return
  emit('update:npcsCanDamageProtagonist', !props.npcsCanDamageProtagonist)
}
</script>

<template>
  <div class="p-4 sm:p-5 md:p-6 bg-rose-500/5 border border-rose-500/10 rounded-2xl space-y-4 md:space-y-6 transition-all">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2 border-b border-white/5 pb-3">
      <div class="flex items-center gap-2 sm:gap-3 min-w-0">
        <div class="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-rose-500/20 flex items-center justify-center text-rose-400 shrink-0">
          <AlertTriangle class="w-4 h-4 sm:w-5 sm:h-5" />
        </div>
        <div class="min-w-0">
          <span class="text-xs sm:text-sm font-black text-white uppercase tracking-wider block truncate">
            Combat Permissions
          </span>
          <span class="text-[10px] text-white/40 uppercase tracking-widest">
            Direct HP damage rules
          </span>
        </div>
      </div>

      <div class="flex items-center gap-2 shrink-0">
        <InfoPopoverButton title="Combat Permissions" :text="CREATE_ADVENTURE_HELP_TEXTS.combatPermissions" />
        <span
          class="px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider border"
          :class="isRpgMode ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'"
        >
          {{ isRpgMode ? 'RPG Mode Active' : 'Requires RPG Mode' }}
        </span>
      </div>
    </div>

    <!-- Disabled State Notice when not in RPG Mode -->
    <div v-if="!isRpgMode" class="flex items-start gap-2.5 p-3 rounded-xl bg-slate-900/60 border border-white/5 text-slate-400 text-xs leading-relaxed">
      <ShieldOff class="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
      <div>
        <span class="font-bold text-slate-300 block">Combat Permissions Disabled</span>
        <span class="text-[11px] text-slate-400 block mt-0.5">
          Combat permissions are only active when <strong>RPG</strong> mode is selected. In Story and Chat modes, encounters and conflicts are resolved narratively without direct player/NPC hit-point damage mechanics.
        </span>
      </div>
    </div>

    <!-- Switches -->
    <div class="space-y-3 md:space-y-4" :class="{ 'opacity-40 pointer-events-none select-none': !isRpgMode }">
      <!-- Protagonist Can Damage NPCs -->
      <div
        class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 rounded-xl border border-white/10 bg-black/20 transition-all"
        :class="isRpgMode ? 'hover:border-rose-500/20' : ''"
      >
        <div class="space-y-1 sm:pr-4 min-w-0">
          <p class="text-xs font-black text-white/80 uppercase tracking-widest">Protagonist Can Damage NPCs</p>
          <p class="text-[10px] text-white/40 uppercase tracking-wider">
            If disabled, no player attack can deal HP damage to NPCs.
          </p>
        </div>
        <div
          @click="toggleCanDamageNpcs"
          :class="[
            'w-10 h-5 rounded-full relative transition-colors shrink-0 self-end sm:self-auto',
            isRpgMode ? 'cursor-pointer' : 'cursor-not-allowed',
            isRpgMode && props.canDamageNpcs ? 'bg-rose-500' : 'bg-slate-700'
          ]"
        >
          <div
            :class="[
              'absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm',
              isRpgMode && props.canDamageNpcs ? 'left-6' : 'left-1'
            ]"
          ></div>
        </div>
      </div>

      <!-- NPCs Can Damage Protagonist -->
      <div
        class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 rounded-xl border border-white/10 bg-black/20 transition-all"
        :class="isRpgMode ? 'hover:border-rose-500/20' : ''"
      >
        <div class="space-y-1 sm:pr-4 min-w-0">
          <p class="text-xs font-black text-white/80 uppercase tracking-widest">NPCs Can Damage Protagonist</p>
          <p class="text-[10px] text-white/40 uppercase tracking-wider">
            If disabled, enemy turns still happen but cannot reduce player HP.
          </p>
        </div>
        <div
          @click="toggleNpcsCanDamageProtagonist"
          :class="[
            'w-10 h-5 rounded-full relative transition-colors shrink-0 self-end sm:self-auto',
            isRpgMode ? 'cursor-pointer' : 'cursor-not-allowed',
            isRpgMode && props.npcsCanDamageProtagonist ? 'bg-rose-500' : 'bg-slate-700'
          ]"
        >
          <div
            :class="[
              'absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm',
              isRpgMode && props.npcsCanDamageProtagonist ? 'left-6' : 'left-1'
            ]"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>
