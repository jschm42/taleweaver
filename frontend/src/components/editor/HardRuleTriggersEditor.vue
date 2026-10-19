<script setup lang="ts">
import { computed } from 'vue'
import { MapPin, Package, ShieldCheck, Swords } from 'lucide-vue-next'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'

export interface HardRule {
  required_item_id?: string | null
  required_scene_id?: string | null
  required_defeated_npc_id?: string | null
  guard_expression?: string | null
}

type RuleKey = 'required_item_id' | 'required_scene_id' | 'required_defeated_npc_id'
type ReferenceOption = { id: string; name?: string; type?: string }

const props = withDefaults(defineProps<{
  modelValue: HardRule
  referenceOptions?: ReferenceOption[]
  title: string
  description: string
  guardLabel?: string
  guardHelp?: string
  itemHint?: string
  sceneHint?: string
  npcHint?: string
}>(), {
  referenceOptions: () => [],
  guardLabel: 'Guard Rule (Python Expression)',
  guardHelp: 'Optional sandboxed Python boolean condition. All configured conditions must be met.',
  itemHint: 'Protagonist acquires item X',
  sceneHint: 'Protagonist enters scene X',
  npcHint: 'Protagonist defeats NPC X',
})

const emit = defineEmits<{
  'update:modelValue': [value: HardRule]
}>()

const fields = computed(() => [
  { key: 'required_item_id' as RuleKey, label: 'Obtain Item', hint: props.itemHint, icon: Package, tone: 'text-emerald-400', type: 'OBJECT' },
  { key: 'required_scene_id' as RuleKey, label: 'Enter Scene', hint: props.sceneHint, icon: MapPin, tone: 'text-sky-400', type: 'SCENE' },
  { key: 'required_defeated_npc_id' as RuleKey, label: 'Defeat NPC', hint: props.npcHint, icon: Swords, tone: 'text-rose-400', type: 'NPC' },
])

function optionsFor(type: string): ReferenceOption[] {
  return props.referenceOptions.filter((o) => (o.type || '').toUpperCase() === type)
}

function update(key: keyof HardRule, value: string): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value || null })
}

function isCustom(key: RuleKey, type: string): boolean {
  const value = props.modelValue[key]
  return !!value && !optionsFor(type).some((o) => o.id === value)
}
</script>

<template>
  <div class="space-y-3 p-4 rounded-2xl bg-black/40 border border-white/5">
    <div class="flex items-center gap-2">
      <ShieldCheck class="w-4 h-4 text-emerald-400" />
      <span class="text-xs font-black text-emerald-400 uppercase tracking-widest">{{ title }}</span>
    </div>
    <p class="text-[11px] text-slate-400">{{ description }}</p>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <div v-for="field in fields" :key="field.key" class="space-y-1.5 p-3 rounded-xl bg-slate-900/80 border border-white/5">
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-1.5 text-[11px] font-bold text-slate-300">
            <component :is="field.icon" :class="['w-3.5 h-3.5', field.tone]" />
            {{ field.label }}
          </span>
          <button
            v-if="modelValue[field.key]"
            type="button"
            class="text-[10px] text-slate-500 hover:text-rose-400"
            @click="update(field.key, '')"
          >Clear</button>
        </div>
        <select
          :value="modelValue[field.key] || ''"
          class="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none"
          @change="update(field.key, ($event.target as HTMLSelectElement).value)"
        >
          <option value="">-- None (Optional) --</option>
          <option v-for="opt in optionsFor(field.type)" :key="opt.id" :value="opt.id">
            {{ opt.name || opt.id }} ({{ opt.id }})
          </option>
          <option v-if="isCustom(field.key, field.type)" :value="modelValue[field.key] || ''">
            {{ modelValue[field.key] }} (Custom ID)
          </option>
        </select>
        <span class="block text-[10px] text-slate-500">{{ field.hint }}</span>
      </div>
    </div>

    <div class="p-3 rounded-xl bg-slate-900/80 border border-white/5">
      <ScriptEditor
        :model-value="modelValue.guard_expression || ''"
        :label="guardLabel"
        :help-text="guardHelp"
        context="guard_expression"
        placeholder="e.g. tw.vars.get('trained_with_master') == True"
        min-height="80px"
        @update:model-value="(v: string) => update('guard_expression', v)"
      />
    </div>
  </div>
</template>
