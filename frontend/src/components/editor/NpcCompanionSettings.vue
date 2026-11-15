<script setup lang="ts">
import { ref, watch } from 'vue'
import { Save, Users } from 'lucide-vue-next'
import {
  companionService,
  DEFAULT_COMPANION,
  type CompanionBanter,
  type CompanionRecruitMode,
  type CompanionSettings,
  type CompanionTactics,
} from '@/services/companionService'

type NpcLike = {
  id: string
  name: string
  metadata_json?: { companion?: Partial<CompanionSettings> | null } | null
}

const props = defineProps<{
  adventureId: string
  npc: NpcLike
}>()

const emit = defineEmits<{
  saved: []
}>()

const TACTICS: Array<{ value: CompanionTactics; label: string }> = [
  { value: 'BALANCED', label: 'Balanced' },
  { value: 'OFFENSIVE', label: 'Offensive (finishes weak enemies)' },
  { value: 'DEFENSIVE', label: 'Defensive (draws attacks)' },
  { value: 'SUPPORT', label: 'Support (heals and helps)' },
]
const BANTER: Array<{ value: CompanionBanter; label: string }> = [
  { value: 'QUIET', label: 'Quiet' },
  { value: 'NORMAL', label: 'Normal' },
  { value: 'CHATTY', label: 'Chatty' },
]

const RECRUIT_MODES: Array<{ value: CompanionRecruitMode; label: string }> = [
  { value: 'SCRIPT', label: 'Only by script (tw.party.recruit)' },
  { value: 'INSTANT', label: 'Recruit action: joins at once' },
  { value: 'ITEM', label: 'Recruit dialog: wants an item' },
]

const isCompanion = ref(false)
const form = ref<CompanionSettings>({ ...DEFAULT_COMPANION })
const saving = ref(false)
const note = ref('')
const error = ref('')

watch(() => [props.npc.id, JSON.stringify(props.npc.metadata_json?.companion ?? null)], () => {
  const stored = props.npc.metadata_json?.companion
  isCompanion.value = Boolean(stored)
  form.value = { ...DEFAULT_COMPANION, ...(stored ?? {}) }
}, { immediate: true })

async function save(): Promise<void> {
  saving.value = true
  note.value = ''
  error.value = ''
  try {
    const recovery = Math.min(1, Math.max(0.01, Number(form.value.downed_recovery) || DEFAULT_COMPANION.downed_recovery))
    if (isCompanion.value && form.value.recruit_mode === 'ITEM' && !form.value.recruit_item_id.trim()) {
      error.value = 'Choose the item the NPC wants (or another recruit mode).'
      return
    }
    await companionService.saveNpcCompanion(
      props.adventureId,
      props.npc.id,
      isCompanion.value
        ? { ...form.value, downed_recovery: recovery, recruit_item_id: form.value.recruit_item_id.trim().toUpperCase() }
        : null,
    )
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
  <section class="space-y-3">
    <h4 class="text-xs font-black text-sky-400 uppercase tracking-[0.2em] flex items-center gap-2">
      <Users class="w-4 h-4" /> Companion · {{ npc.name }}
    </h4>

    <div class="flex items-center justify-between p-4 bg-black/30 border border-white/10 rounded-2xl">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-sky-400 uppercase tracking-widest">Can be a companion</p>
        <p class="text-[11px] text-slate-400">
          The NPC can join the protagonist's party and follows them through exits.
          Exits and chapters marked as solo leave the companion behind.
          In combat it uses its special actions from "Combat Profile &amp; Specials"; players can switch them off and equip it in the hero dialog.
        </p>
      </div>
      <button
        type="button"
        role="switch"
        :aria-checked="isCompanion"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1 shrink-0', isCompanion ? 'bg-sky-600' : 'bg-slate-700']"
        @click="isCompanion = !isCompanion"
      >
        <span :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', isCompanion ? 'translate-x-6' : 'translate-x-0']"></span>
      </button>
    </div>

    <div v-if="isCompanion" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <label class="flex items-start gap-2 text-xs text-slate-300 cursor-pointer sm:col-span-2" title="Only one companion can be active. If several NPCs start in the party, the first one travels with the protagonist.">
        <input v-model="form.starts_in_party" type="checkbox" class="mt-0.5 accent-sky-500" />
        <span>
          In the party from the start
          <span class="block text-[11px] text-slate-500">The companion starts next to the protagonist in the first scene.</span>
        </span>
      </label>
      <label class="text-xs text-slate-300 space-y-1 block">
        <span>Combat tactics</span>
        <select v-model="form.tactics" class="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none">
          <option v-for="opt in TACTICS" :key="opt.value" :value="opt.value" class="bg-slate-900">{{ opt.label }}</option>
        </select>
      </label>
      <label class="text-xs text-slate-300 space-y-1 block">
        <span>Banter</span>
        <select v-model="form.banter" class="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none">
          <option v-for="opt in BANTER" :key="opt.value" :value="opt.value" class="bg-slate-900">{{ opt.label }}</option>
        </select>
      </label>
      <label class="text-xs text-slate-300 space-y-1 block sm:col-span-2">
        <span>How the player recruits it</span>
        <select v-model="form.recruit_mode" class="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none">
          <option v-for="opt in RECRUIT_MODES" :key="opt.value" :value="opt.value" class="bg-slate-900">{{ opt.label }}</option>
        </select>
        <span class="block text-[11px] text-slate-500">
          With a Recruit action the NPC shows a companion frame and tag in-game. In the item dialog only the item below convinces it; the NPC keeps that item. Success and failure narration: the NPC's "On Recruit" triggers.
        </span>
      </label>
      <label v-if="form.recruit_mode === 'ITEM'" class="text-xs text-slate-300 space-y-1 block">
        <span>Wanted item ID</span>
        <input
          v-model="form.recruit_item_id"
          type="text"
          placeholder="e.g. BOTTLE_OF_RUM"
          class="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none uppercase"
        />
      </label>
      <label v-if="form.recruit_mode !== 'SCRIPT'" class="text-xs text-slate-300 space-y-1 block" :class="form.recruit_mode === 'ITEM' ? '' : 'sm:col-span-2'">
        <span>Dialog hint (optional)</span>
        <input
          v-model="form.recruit_hint"
          type="text"
          maxlength="300"
          placeholder="e.g. Bring me something strong to drink."
          class="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none"
        />
      </label>
      <label class="text-xs text-slate-300 space-y-1 block sm:col-span-2" title="When the companion drops to 0 HP in a fight it is downed, not killed. After the fight it gets this share of its max HP back.">
        <span>HP after being downed (share of max HP, 0.01–1)</span>
        <input
          v-model.number="form.downed_recovery"
          type="number"
          min="0.01"
          max="1"
          step="0.05"
          class="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none"
        />
      </label>
    </div>

    <div class="flex items-center gap-3">
      <button
        type="button"
        :disabled="saving"
        class="flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-xs font-bold text-white"
        @click="save"
      >
        <Save class="w-4 h-4" /> Save companion
      </button>
      <span v-if="note" class="text-[11px] text-emerald-400">{{ note }}</span>
      <span v-if="error" class="text-[11px] text-rose-400">{{ error }}</span>
    </div>
  </section>
</template>
