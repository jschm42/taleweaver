<script setup lang="ts">
import { computed } from 'vue'
import type { Talent } from '@/types'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import HardRuleTriggersEditor, { type HardRule } from '@/components/editor/HardRuleTriggersEditor.vue'
import { TALENT_TARGET_LABELS, TALENT_TARGET_TYPES } from '@/utils/talents'

export type TalentDraft = Talent & { _key: number }

defineProps<{
  referenceOptions?: Array<{ id: string; name?: string; type?: string }>
}>()

const draft = defineModel<TalentDraft>({ required: true })

const inputClass = 'w-full bg-slate-900 border border-white/10 rounded-lg px-2 py-1.5 text-white'

const unlockRule = computed<HardRule>({
  get: () => ({
    required_item_id: draft.value.unlock_required_item_id,
    required_scene_id: draft.value.unlock_required_scene_id,
    required_defeated_npc_id: draft.value.unlock_required_defeated_npc_id,
    guard_expression: draft.value.unlock_guard_expression,
  }),
  set: (rule) => {
    draft.value.unlock_required_item_id = rule.required_item_id || null
    draft.value.unlock_required_scene_id = rule.required_scene_id || null
    draft.value.unlock_required_defeated_npc_id = rule.required_defeated_npc_id || null
    draft.value.unlock_guard_expression = rule.guard_expression || null
  },
})
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-3 px-3 pb-3 text-xs">
    <label class="space-y-1">
      <span class="text-slate-400 font-bold">Name (what the player types)</span>
      <input v-model="draft.name" maxlength="60" :class="inputClass" />
    </label>
    <label class="space-y-1">
      <span class="text-slate-400 font-bold">ID</span>
      <input v-model="draft.id" :class="[inputClass, 'font-mono uppercase']" />
    </label>
    <label class="space-y-1 md:col-span-2">
      <span class="text-slate-400 font-bold">Description</span>
      <input v-model="draft.description" :class="inputClass" />
    </label>
    <label class="space-y-1">
      <span class="text-slate-400 font-bold">Used on</span>
      <select v-model="draft.target_type" :class="inputClass">
        <option v-for="t in TALENT_TARGET_TYPES" :key="t" :value="t">{{ TALENT_TARGET_LABELS[t] }}</option>
      </select>
    </label>
    <div class="flex gap-2">
      <label class="space-y-1 flex-1">
        <span class="text-slate-400 font-bold">Cost</span>
        <input v-model.number="draft.cost" type="number" min="0" max="999" :class="inputClass" />
      </label>
      <label class="space-y-1 flex-1">
        <span class="text-slate-400 font-bold">Paid with</span>
        <select v-model="draft.cost_type" :class="inputClass">
          <option value="mana">Mana</option>
          <option value="stamina">Stamina</option>
        </select>
      </label>
      <label class="space-y-1 flex-1">
        <span class="text-slate-400 font-bold">Uses / adventure</span>
        <input v-model.number="draft.max_uses" type="number" min="1" max="99" placeholder="∞" :class="inputClass" />
      </label>
    </div>
    <label class="space-y-1 md:col-span-2">
      <span class="text-slate-400 font-bold">Game Master instruction</span>
      <textarea
        v-model="draft.gm_hint"
        rows="2"
        placeholder="e.g. Reveal the target's true thoughts in one italic sentence."
        :class="inputClass"
      ></textarea>
      <span class="block text-[10px] text-slate-500">Tells the Game Master what the talent reveals or causes when it narrates the use.</span>
    </label>
    <label class="space-y-1 md:col-span-2">
      <span class="text-slate-400 font-bold">Text on use (optional)</span>
      <input v-model="draft.on_use_text" placeholder="e.g. A faint hum fills your head." :class="inputClass" />
    </label>
    <div class="md:col-span-2">
      <ScriptEditor
        :model-value="draft.on_use_script ?? ''"
        @update:model-value="(v: string) => (draft.on_use_script = v)"
        label="On Use Script (optional)"
        help-text="Runs on every successful use, before the Game Master narrates. `talent` holds id, name, target_id, target_name, target_type, uses and uses_left."
        min-height="90px"
      />
    </div>

    <div class="md:col-span-2 space-y-2">
      <label class="flex items-center gap-2 text-slate-300 font-bold">
        <input v-model="draft.is_locked" type="checkbox" class="accent-violet-500" /> Starts locked
      </label>
      <template v-if="draft.is_locked">
        <HardRuleTriggersEditor
          v-model="unlockRule"
          :reference-options="referenceOptions"
          title="Unlock Conditions (Hard Rules)"
          description="The talent unlocks automatically once every configured condition is met. A system message announces it."
          guard-label="Unlock Guard (Python Expression)"
          guard-help="Optional sandboxed Python condition, e.g. tw.vars.get('met_the_oracle') == True."
        />
        <label class="block space-y-1">
          <span class="text-slate-400 font-bold">Unlock message (optional)</span>
          <input v-model="draft.unlock_text" placeholder="e.g. The oracle's whisper still echoes in your mind." :class="inputClass" />
        </label>
      </template>
    </div>
  </div>
</template>
