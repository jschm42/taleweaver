<script setup lang="ts">
/** Play style (rule enforcement) and, in advanced mode, the combat damage rules of RPG mode. */
import { computed } from 'vue'
import { BookOpen, MessageCircle, Swords } from 'lucide-vue-next'
import { useCreateAdventureContext } from '@/composables/createAdventure/createAdventureContext'
import type { RuleMode } from '@/composables/createAdventure/createAdventureForm'
import UiCard from '@/components/ui/UiCard.vue'
import UiRadioCards, { type RadioCardOption } from '@/components/ui/UiRadioCards.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const { form, mode } = useCreateAdventureContext()

const MODES: RadioCardOption<RuleMode>[] = [
  { value: 'rpg', label: 'RPG', icon: Swords, description: 'Strict rules, inventory checks, dice and combat.' },
  { value: 'story', label: 'Story', icon: BookOpen, description: 'Narrative first, with balanced mechanics.' },
  { value: 'chat', label: 'Chat', icon: MessageCircle, description: 'Free roleplay without rule or combat barriers.' },
]

const isRpg = computed(() => form.value.rule_enforcement_mode === 'rpg')
const combatHint = computed(() => (isRpg.value ? '' : 'Only in RPG mode. Story and Chat resolve conflicts in the narration.'))
</script>

<template>
  <UiCard title="Play style" description="How strictly the Game Master applies rules during play.">
    <div class="space-y-5">
      <UiRadioCards v-model="form.rule_enforcement_mode" :options="MODES" label="Play style" :columns="3" />
      <div v-if="mode === 'advanced'" class="space-y-3 border-t border-wb-line pt-4">
        <p class="wb-subheading">Combat damage</p>
        <p v-if="combatHint" class="wb-hint">{{ combatHint }}</p>
        <UiToggle
          v-model="form.can_damage_npcs"
          label="The protagonist can hurt characters"
          description="Off: player attacks never reduce a character's HP."
          :disabled="!isRpg"
        />
        <UiToggle
          v-model="form.npcs_can_damage_protagonist"
          label="Characters can hurt the protagonist"
          description="Off: enemies still act, but the protagonist's HP stays."
          :disabled="!isRpg"
        />
      </div>
    </div>
  </UiCard>
</template>
