<script setup lang="ts">
import { ref } from 'vue'
import { Save } from 'lucide-vue-next'
import UiButton from '@/components/ui/UiButton.vue'
import UiSection from '@/components/ui/UiSection.vue'
import NpcAttributeFields from '@/components/editor/NpcAttributeFields.vue'
import NpcMainAttackFields from '@/components/editor/NpcMainAttackFields.vue'
import { useNpcCombatProfile, type NpcCombatProfileState, type NpcProfileSource } from '@/composables/editor/useNpcCombatProfile'

/**
 * Combat profile: attributes, armor and main attack. With `profile` it shows only the main attack
 * of a profile its parent keeps (the entity form puts the attributes on its Stats tab); without,
 * it keeps its own profile and shows everything.
 */
const props = defineProps<{
  adventureId: string
  npc: NpcProfileSource
  profile?: NpcCombatProfileState | null
}>()

const emit = defineEmits<{ saved: [] }>()

const own = props.profile ? null : useNpcCombatProfile(() => props.adventureId, () => props.npc)
const state = (props.profile ?? own) as NpcCombatProfileState
const showAttributes = !props.profile

const saving = ref(false)
const note = ref('')
const error = ref('')

async function save(): Promise<void> {
  if (state.problems.value.length) return
  saving.value = true
  note.value = ''
  error.value = ''
  try {
    await state.persist()
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
  <UiSection
    :title="showAttributes ? 'Combat profile' : 'Main attack'"
    :description="showAttributes ? 'Stats, armor and the main attack this character fights with.' : 'The attack this character fights with. Attributes and AC are on the Stats tab.'"
  >
    <NpcAttributeFields v-if="showAttributes" :profile="state" />
    <NpcMainAttackFields :profile="state" />

    <div class="flex flex-wrap items-center gap-3">
      <UiButton v-if="!state.embedded" :icon="Save" :loading="saving" :disabled="state.problems.value.length > 0" @click="save">
        Save combat profile
      </UiButton>
      <span v-if="note" class="wb-hint !text-wb-accent-text" role="status">{{ note }}</span>
      <span v-if="error" class="wb-hint !text-wb-danger-text" role="alert">{{ error }}</span>
      <span v-for="p in state.problems.value" :key="p" class="wb-hint !text-wb-warn-text">{{ p }}</span>
    </div>
  </UiSection>
</template>
