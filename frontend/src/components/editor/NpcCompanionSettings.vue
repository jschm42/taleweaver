<script setup lang="ts">
import { ref, watch } from 'vue'
import { Save } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSection from '@/components/ui/UiSection.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import {
  companionService,
  DEFAULT_COMPANION,
  type CompanionBanter,
  type CompanionRecruitMode,
  type CompanionSettings,
  type CompanionTactics,
} from '@/services/companionService'
import { useEntitySubform } from '@/components/editor/entity/entitySubforms'

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

// Last loaded state, to tell whether the settings changed.
const loaded = ref('')

function companionPayload(): CompanionSettings | null {
  if (!isCompanion.value) return null
  const recovery = Math.min(1, Math.max(0.01, Number(form.value.downed_recovery) || DEFAULT_COMPANION.downed_recovery))
  return { ...form.value, downed_recovery: recovery, recruit_item_id: form.value.recruit_item_id.trim().toUpperCase() }
}

function validationError(): string | null {
  if (isCompanion.value && form.value.recruit_mode === 'ITEM' && !form.value.recruit_item_id.trim()) {
    return 'Choose the item the NPC wants (or another recruit mode).'
  }
  return null
}

watch(() => [props.npc.id, JSON.stringify(props.npc.metadata_json?.companion ?? null)], () => {
  const stored = props.npc.metadata_json?.companion
  isCompanion.value = Boolean(stored)
  form.value = { ...DEFAULT_COMPANION, ...(stored ?? {}) }
  loaded.value = JSON.stringify(companionPayload())
}, { immediate: true })

async function persist(): Promise<void> {
  const problem = validationError()
  if (problem) throw new Error(problem)
  await companionService.saveNpcCompanion(props.adventureId, props.npc.id, companionPayload())
  loaded.value = JSON.stringify(companionPayload())
}

// Inside the entity form, "Save changes" saves these settings; elsewhere the own button does.
const embedded = useEntitySubform({
  label: 'Companion',
  isDirty: () => JSON.stringify(companionPayload()) !== loaded.value,
  error: validationError,
  save: persist,
})

async function save(): Promise<void> {
  saving.value = true
  note.value = ''
  error.value = ''
  try {
    await persist()
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
  <UiSection title="Companion" :description="`Whether ${npc.name} can join the protagonist's party.`">
    <UiToggle
      v-model="isCompanion"
      label="Can be a companion"
      description="Joins the party and follows the protagonist through exits; solo exits and chapters leave it behind. Players can equip it and switch its specials off in the hero dialog."
    />

    <div v-if="isCompanion" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <UiCheckbox
        v-model="form.starts_in_party"
        label="In the party from the start"
        description="Starts next to the protagonist in the first scene. Only one companion is active; with several, the first one travels along."
        class="sm:col-span-2"
      />
      <UiField label="Combat tactics">
        <UiSelect v-model="form.tactics" :options="TACTICS" />
      </UiField>
      <UiField label="Banter">
        <UiSelect v-model="form.banter" :options="BANTER" />
      </UiField>
      <UiField
        label="How the player recruits it"
        class="sm:col-span-2"
        hint="Success and failure narration: the 'On recruit' triggers below."
        info="With a Recruit action the character shows a companion frame and tag in-game. In the item dialog only the item below convinces it; it keeps that item."
      >
        <UiSelect v-model="form.recruit_mode" :options="RECRUIT_MODES" />
      </UiField>
      <UiField v-if="form.recruit_mode === 'ITEM'" label="Wanted item ID">
        <UiInput v-model="form.recruit_item_id" class="uppercase placeholder:normal-case" mono placeholder="e.g. BOTTLE_OF_RUM" />
      </UiField>
      <UiField v-if="form.recruit_mode !== 'SCRIPT'" label="Dialog hint" hint="Optional." :class="form.recruit_mode === 'ITEM' ? '' : 'sm:col-span-2'">
        <UiInput v-model="form.recruit_hint" maxlength="300" placeholder="e.g. Bring me something strong to drink." />
      </UiField>
      <UiField
        label="HP after being downed"
        hint="Share of max HP, 0.01–1."
        info="At 0 HP in a fight the companion is downed, not killed. After the fight it gets this share of its max HP back."
        class="sm:col-span-2"
      >
        <UiInput
          type="number"
          min="0.01"
          max="1"
          step="0.05"
          :model-value="form.downed_recovery"
          @update:model-value="(value) => (form.downed_recovery = Number(value ?? 0))"
        />
      </UiField>
    </div>

    <div class="flex items-center gap-3">
      <UiButton v-if="!embedded" :icon="Save" :loading="saving" @click="save">Save companion</UiButton>
      <span v-if="note" class="wb-hint !text-wb-accent-text" role="status">{{ note }}</span>
      <span v-if="error" class="wb-hint !text-wb-danger-text" role="alert">{{ error }}</span>
    </div>
  </UiSection>
</template>
