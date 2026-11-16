<script setup lang="ts">
// Editor setting for AdventureTemplate.game_over_rules: what happens when the protagonist falls
// to 0 HP. "game_over" ends the adventure; "respawn" revives them at the last revival point
// reached (else the start scene) with a share of their max HP.
import { computed, ref, watch } from 'vue'

type GameOverRules = { on_zero_hp?: string; respawn_hp_percent?: number; [key: string]: unknown }

const props = defineProps<{
  modelValue: GameOverRules | null | undefined
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'save', value: GameOverRules): void
}>()

const DEFAULT_PERCENT = 25

const respawn = ref(false)
const percent = ref(DEFAULT_PERCENT)

function load(): void {
  respawn.value = props.modelValue?.on_zero_hp === 'respawn'
  percent.value = Number(props.modelValue?.respawn_hp_percent ?? DEFAULT_PERCENT) || DEFAULT_PERCENT
}

watch(() => props.modelValue, load, { immediate: true, deep: true })

const clampedPercent = computed(() => Math.max(1, Math.min(100, Math.round(Number(percent.value) || DEFAULT_PERCENT))))

const dirty = computed(() => {
  const storedRespawn = props.modelValue?.on_zero_hp === 'respawn'
  const storedPercent = Number(props.modelValue?.respawn_hp_percent ?? DEFAULT_PERCENT)
  return storedRespawn !== respawn.value || (respawn.value && storedPercent !== clampedPercent.value)
})

function save(): void {
  emit('save', {
    ...(props.modelValue ?? {}),
    on_zero_hp: respawn.value ? 'respawn' : 'game_over',
    respawn_hp_percent: clampedPercent.value,
  })
}
</script>

<template>
  <div class="space-y-3 pt-2 border-t border-red-500/10">
    <div class="flex items-start justify-between gap-4">
      <div class="space-y-1 min-w-0">
        <span class="block text-[10px] font-bold tracking-widest uppercase text-red-400">At 0 HP</span>
        <p class="text-[10px] text-slate-500">
          <template v-if="respawn">
            The protagonist is knocked out and wakes up at the last revival point reached (scenes marked
            as revival points, else the start scene). Status effects are cleared; enemies keep their HP.
            Penalties can be scripted with the <code>on_respawn</code> trigger.
          </template>
          <template v-else>
            Falling to 0 HP ends the adventure (Game Over).
          </template>
        </p>
      </div>
      <div class="flex shrink-0 rounded-lg bg-black/40 border border-white/10 p-0.5">
        <button
          type="button"
          class="px-3 py-1 text-[10px] font-black uppercase tracking-widest rounded-md transition-colors"
          :class="!respawn ? 'bg-red-600 text-white' : 'text-slate-500 hover:text-slate-300'"
          @click="respawn = false"
        >Game Over</button>
        <button
          type="button"
          class="px-3 py-1 text-[10px] font-black uppercase tracking-widest rounded-md transition-colors"
          :class="respawn ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-slate-300'"
          @click="respawn = true"
        >Respawn</button>
      </div>
    </div>
    <label v-if="respawn" class="flex items-center gap-3 text-xs text-slate-400">
      Revive with
      <input
        v-model.number="percent"
        type="number"
        min="1"
        max="100"
        class="w-16 bg-black/40 border border-white/10 rounded-md px-2 py-1 text-slate-200 text-xs"
      />
      % of max HP
    </label>
    <button
      v-if="dirty"
      type="button"
      class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all"
      :disabled="saving"
      @click="save"
    >Save</button>
  </div>
</template>
