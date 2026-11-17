<script setup lang="ts">
import { computed } from 'vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import type { SelectOption } from '@/components/ui/UiSelect.vue'

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
  guardLabel: 'Guard rule (Python expression)',
  guardHelp: 'Optional sandboxed Python boolean condition. All configured conditions must be met.',
  itemHint: 'Protagonist acquires item X',
  sceneHint: 'Protagonist enters scene X',
  npcHint: 'Protagonist defeats NPC X',
})

const emit = defineEmits<{
  'update:modelValue': [value: HardRule]
}>()

const fields = computed(() => [
  { key: 'required_item_id' as RuleKey, label: 'Obtain item', hint: props.itemHint, type: 'OBJECT' },
  { key: 'required_scene_id' as RuleKey, label: 'Enter scene', hint: props.sceneHint, type: 'SCENE' },
  { key: 'required_defeated_npc_id' as RuleKey, label: 'Defeat character', hint: props.npcHint, type: 'NPC' },
])

function optionsFor(type: string): ReferenceOption[] {
  return props.referenceOptions.filter((o) => (o.type || '').toUpperCase() === type)
}

function selectOptions(key: RuleKey, type: string): SelectOption[] {
  const options: SelectOption[] = [
    { value: '', label: 'None' },
    ...optionsFor(type).map((o) => ({ value: o.id, label: `${o.name || o.id} (${o.id})` })),
  ]
  if (isCustom(key, type)) options.push({ value: props.modelValue[key] || '', label: `${props.modelValue[key]} (custom ID)` })
  return options
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
  <UiSection :title="title" :description="description">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <UiField v-for="field in fields" :key="field.key" :label="field.label" :hint="field.hint">
        <UiSelect
          :model-value="modelValue[field.key] || ''"
          :options="selectOptions(field.key, field.type)"
          @update:model-value="(value) => update(field.key, String(value ?? ''))"
        />
      </UiField>
    </div>

    <ScriptEditor
      :model-value="modelValue.guard_expression || ''"
      :label="guardLabel"
      :help-text="guardHelp"
      context="guard_expression"
      placeholder="e.g. tw.vars.get('trained_with_master') == True"
      min-height="80px"
      @update:model-value="(v: string) => update('guard_expression', v)"
    />
  </UiSection>
</template>
