<script setup lang="ts">
import { Lock, Plus, Trash2, Unlock } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

/**
 * State list of a SWITCH: each state has an ID (script key, max 15 characters: A-Z, 0-9, _ and -)
 * and an optional label (max 20 characters) shown to the player. Without a label the ID is shown.
 * Renames and removals are emitted so the parent can keep transitions and the initial state in sync.
 */
const props = defineProps<{
  states: string[]
  labels: Record<string, string>
  disabledStates?: string[]
}>()

const emit = defineEmits<{
  (e: 'add'): void
  (e: 'remove', index: number): void
  (e: 'rename', index: number, value: string): void
  (e: 'update:labels', value: Record<string, string>): void
  (e: 'update:disabledStates', value: string[]): void
}>()

const STATE_ID_MAX = 15
const STATE_LABEL_MAX = 20

function setLabel(state: string, value: string) {
  const next = { ...props.labels }
  const text = value.slice(0, STATE_LABEL_MAX)
  if (text.trim()) {
    next[state] = text
  } else {
    delete next[state]
  }
  emit('update:labels', next)
}

function isStateDisabled(state: string): boolean {
  const clean = String(state || '').trim().toUpperCase()
  return Boolean(clean && (props.disabledStates || []).includes(clean))
}

function toggleDisabled(state: string) {
  const clean = String(state || '').trim().toUpperCase()
  if (!clean) return
  const current = [...(props.disabledStates || [])]
  const next = current.includes(clean)
    ? current.filter((s) => s !== clean)
    : [...current, clean]
  emit('update:disabledStates', next)
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-3">
      <p class="wb-subheading">Switch states</p>
      <span class="wb-hint">At least 2 required</span>
    </div>
    <div class="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto_auto] gap-2 px-1 wb-hint">
      <span>ID (scripts)</span>
      <span>In-game text (optional)</span>
      <span class="w-8 text-center">Lock</span>
      <span class="w-8" />
    </div>

    <div class="space-y-2">
      <div
        v-for="(state, idx) in states"
        :key="idx"
        class="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto_auto] items-center gap-2"
      >
        <UiInput
          :model-value="state"
          :maxlength="STATE_ID_MAX"
          mono
          placeholder="e.g. HALF-OPEN"
          :aria-label="`State ${idx + 1} ID`"
          @update:model-value="(value) => emit('rename', idx, String(value ?? ''))"
        />
        <UiInput
          :model-value="labels[state] || ''"
          :maxlength="STATE_LABEL_MAX"
          :placeholder="state || 'Label'"
          :aria-label="`State ${idx + 1} in-game text`"
          @update:model-value="(value) => setLabel(state, String(value ?? ''))"
        />
        <UiIconButton
          :icon="isStateDisabled(state) ? Lock : Unlock"
          :variant="isStateDisabled(state) ? 'secondary' : 'ghost'"
          :label="isStateDisabled(state) ? 'Starts locked; scripts can enable it. Click to unlock.' : 'Starts enabled. Click to lock it by default.'"
          :aria-pressed="isStateDisabled(state)"
          @click="toggleDisabled(state)"
        />
        <UiIconButton :icon="Trash2" label="Remove state" variant="danger" :disabled="states.length <= 2" @click="emit('remove', idx)" />
      </div>
    </div>

    <UiButton size="sm" :icon="Plus" @click="emit('add')">Add state</UiButton>
    <p class="wb-hint">
      The ID is used by scripts, transitions and gates (up to {{ STATE_ID_MAX }} characters: letters, digits, "_" and "-").
      The in-game text (up to {{ STATE_LABEL_MAX }}) is what the player sees; without it the ID is shown.
    </p>
  </div>
</template>
