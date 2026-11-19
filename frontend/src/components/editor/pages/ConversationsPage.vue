<script setup lang="ts">
/**
 * NPC conversations: whether present characters talk with each other on their own, and whether
 * they pass on what they remember about the protagonist (gossip). Saved through the editor's
 * save bar. Relations and topics are set per character (Characters → Conversations tab).
 */
import { computed } from 'vue'
import { useEditor } from '@/composables/editor/editorContext'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

type ChatterLevel = 'OFF' | 'RARE' | 'NORMAL' | 'LIVELY'

const LEVELS: { value: ChatterLevel; label: string }[] = [
  { value: 'OFF', label: 'Off' },
  { value: 'RARE', label: 'Rare' },
  { value: 'NORMAL', label: 'Normal' },
  { value: 'LIVELY', label: 'Lively' },
]

const editor = useEditor()

function settings(): { chatter: ChatterLevel; gossip: boolean } {
  const raw = (editor.form.npc_conversations ?? {}) as { chatter?: string; gossip?: boolean }
  const chatter = LEVELS.some((level) => level.value === raw.chatter) ? (raw.chatter as ChatterLevel) : 'OFF'
  return { chatter, gossip: Boolean(raw.gossip) }
}

function store(next: { chatter: ChatterLevel; gossip: boolean }): void {
  editor.form.npc_conversations = next.chatter === 'OFF' && !next.gossip ? null : next
}

const chatter = computed<ChatterLevel>({
  get: () => settings().chatter,
  set: (value) => store({ ...settings(), chatter: value }),
})

const gossip = computed<boolean>({
  get: () => settings().gossip,
  set: (value) => store({ ...settings(), gossip: value }),
})
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="NPC conversations" description="Characters who talk with each other, not only with the protagonist." />
    <UiCard title="Chatter">
      <div class="space-y-6">
        <UiField
          label="NPCs start conversations on their own"
          hint="Off: characters only talk with each other when the player listens (/listen)."
          info="Rare, Normal and Lively set how often two present characters talk with each other while the player does not address anyone (after five, three or two such actions); Normal and Lively also start a short talk when the player enters a scene. Players can switch chatter off in the in-game settings. Open conversation topics of the characters come up first."
        >
          <UiSegmented v-model="chatter" :options="LEVELS" label="Chatter level" />
        </UiField>
        <UiToggle
          v-model="gossip"
          label="Gossip"
          description="Characters with memory tell friends, family and colleagues in the same place what they know about the protagonist."
        />
      </div>
    </UiCard>
  </div>
</template>
