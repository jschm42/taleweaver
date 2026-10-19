<script setup lang="ts">
import { ref, watch } from 'vue'
import { Save, Swords } from 'lucide-vue-next'
import type { SpecialAttack } from '@/types'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import SpecialAttacksEditor from '@/components/editor/SpecialAttacksEditor.vue'
import { specialAttackService } from '@/services/specialAttackService'

type NpcLike = {
  id: string
  name: string
  metadata_json?: {
    attack_mode?: string
    attack_trigger?: HardRule | null
    special_chance?: number
    special_actions?: SpecialAttack[]
  } | null
}

const props = defineProps<{
  adventureId: string
  npc: NpcLike
  referenceOptions?: Array<{ id: string; name?: string; type?: string }>
}>()

const emit = defineEmits<{
  saved: []
}>()

const attackOnSight = ref(false)
const trigger = ref<HardRule>({})
const specialChance = ref(40)
const saving = ref(false)
const note = ref('')
const error = ref('')

watch(() => [props.npc.id, JSON.stringify(props.npc.metadata_json ?? {})], () => {
  const meta = props.npc.metadata_json ?? {}
  attackOnSight.value = meta.attack_mode === 'ATTACK_ON_SIGHT'
  trigger.value = { ...(meta.attack_trigger ?? {}) }
  specialChance.value = typeof meta.special_chance === 'number' ? meta.special_chance : 40
}, { immediate: true })

async function saveBehaviour(): Promise<void> {
  saving.value = true
  note.value = ''
  error.value = ''
  try {
    const hasRule = Object.values(trigger.value).some((v) => !!String(v ?? '').trim())
    await specialAttackService.saveNpcCombat(props.adventureId, props.npc.id, {
      attack_mode: attackOnSight.value ? 'ATTACK_ON_SIGHT' : 'PASSIVE',
      attack_trigger: hasRule ? trigger.value : null,
      special_chance: specialChance.value,
    })
    note.value = 'Saved.'
    emit('saved')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-5">
    <section class="space-y-3">
      <h4 class="text-xs font-black text-rose-400 uppercase tracking-[0.2em] flex items-center gap-2">
        <Swords class="w-4 h-4" /> Aggression · {{ npc.name }}
      </h4>

      <div class="flex items-center justify-between p-4 bg-black/30 border border-white/10 rounded-2xl">
        <div class="space-y-1 pr-4">
          <p class="text-xs font-black text-red-400 uppercase tracking-widest">Attack on sight</p>
          <p class="text-[11px] text-slate-400">The NPC starts a fight as soon as the protagonist enters its scene.</p>
        </div>
        <button
          type="button"
          role="switch"
          :aria-checked="attackOnSight"
          :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1 shrink-0', attackOnSight ? 'bg-red-600' : 'bg-slate-700']"
          @click="attackOnSight = !attackOnSight"
        >
          <span :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', attackOnSight ? 'translate-x-6' : 'translate-x-0']"></span>
        </button>
      </div>

      <HardRuleTriggersEditor
        v-model="trigger"
        :reference-options="referenceOptions"
        title="Attack Trigger (Hard Rules)"
        description="Optional: the NPC attacks once when all configured conditions are met while the protagonist is in its scene, e.g. when a certain item is picked up."
        guard-label="Attack Guard (Python Expression)"
        guard-help="Optional sandboxed Python condition, e.g. tw.player.has_item('IDOL') and not tw.vars.get('bribed_guard')."
        item-hint="Protagonist holds item X"
        scene-hint="Protagonist has reached scene X"
        npc-hint="Protagonist has defeated NPC X"
      />

      <label class="block space-y-1.5 p-4 bg-black/30 border border-white/10 rounded-2xl">
        <span class="flex items-center justify-between text-xs font-bold text-slate-300">
          Special attack chance per turn
          <span class="font-mono text-rose-300">{{ specialChance }}%</span>
        </span>
        <input v-model.number="specialChance" type="range" min="0" max="100" step="5" class="w-full accent-rose-500" />
        <span class="block text-[10px] text-slate-500">How often the NPC picks one of its special attacks at random instead of a weapon attack. Badly hurt NPCs prefer healing specials.</span>
      </label>

      <div class="flex items-center gap-3">
        <button
          type="button"
          class="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-black uppercase tracking-wider flex items-center gap-2 disabled:opacity-40"
          :disabled="saving"
          @click="saveBehaviour"
        >
          <Save class="w-3.5 h-3.5" /> {{ saving ? 'Saving…' : 'Save Aggression' }}
        </button>
        <span v-if="note" class="text-xs text-emerald-400">{{ note }}</span>
        <span v-if="error" class="text-xs text-rose-400">{{ error }}</span>
      </div>
    </section>

    <section class="pt-4 border-t border-white/5">
      <SpecialAttacksEditor
        :adventure-id="adventureId"
        target-type="npc"
        :target-id="npc.id"
        :owner-name="npc.name"
        :attacks="npc.metadata_json?.special_actions ?? []"
        :reference-options="referenceOptions"
        @saved="emit('saved')"
      />
    </section>
  </div>
</template>
