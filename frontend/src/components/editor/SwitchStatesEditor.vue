<script setup lang="ts">
import { Plus, Trash2 } from 'lucide-vue-next'

/**
 * State list of a SWITCH: each state has an ID (script key, max 15 characters: A-Z, 0-9, _ and -)
 * and an optional label (max 20 characters) shown to the player. Without a label the ID is shown.
 * Renames and removals are emitted so the parent can keep transitions and the initial state in sync.
 */
const props = defineProps<{
  states: string[]
  labels: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'add'): void
  (e: 'remove', index: number): void
  (e: 'rename', index: number, value: string): void
  (e: 'update:labels', value: Record<string, string>): void
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
</script>

<template>
  <div class="space-y-3 bg-black/20 border border-white/5 p-4 rounded-2xl">
    <div class="flex justify-between items-center">
      <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Switch States</label>
      <span class="text-[10px] text-slate-500 font-bold uppercase tracking-wider">At least 2 required</span>
    </div>
    <div class="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto] gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest px-1">
      <span>ID (scripts)</span>
      <span>In-game text (optional)</span>
      <span class="w-9"></span>
    </div>

    <div class="space-y-2">
      <div
        v-for="(state, idx) in states"
        :key="idx"
        class="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto] gap-2 items-center"
      >
        <input
          :value="state"
          :maxlength="STATE_ID_MAX"
          placeholder="e.g. HALF-OPEN"
          class="min-w-0 bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-sm text-white font-mono font-bold focus:border-lime-500 outline-none transition-all"
          @input="(e) => emit('rename', idx, (e.target as HTMLInputElement).value)"
        />
        <input
          :value="labels[state] || ''"
          :maxlength="STATE_LABEL_MAX"
          :placeholder="state || 'Label'"
          class="min-w-0 bg-black/40 border border-white/5 rounded-xl px-3 py-2 text-sm text-slate-200 focus:border-lime-500 outline-none transition-all"
          @input="(e) => setLabel(state, (e.target as HTMLInputElement).value)"
        />
        <button
          type="button"
          :disabled="states.length <= 2"
          class="shrink-0 px-2.5 py-2 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 text-xs font-bold uppercase tracking-widest transition-all disabled:opacity-30 disabled:hover:bg-transparent"
          title="Remove State"
          @click="emit('remove', idx)"
        >
          <Trash2 class="w-4 h-4" />
        </button>
      </div>

      <button
        type="button"
        class="w-full py-2 bg-lime-500/5 border border-lime-500/10 hover:bg-lime-500/10 hover:border-lime-500/30 rounded-xl text-[10px] font-black text-lime-400 uppercase tracking-widest flex items-center justify-center gap-1.5 transition-all"
        @click="emit('add')"
      >
        <Plus class="w-3.5 h-3.5" /> Add State
      </button>
    </div>
    <p class="text-[10px] text-slate-500 leading-normal">
      The ID is used by scripts, transitions and gates (max. {{ STATE_ID_MAX }} characters: letters, digits, "_" and "-").
      The in-game text (max. {{ STATE_LABEL_MAX }} characters) is what the player sees; without it the ID is shown.
    </p>
  </div>
</template>
