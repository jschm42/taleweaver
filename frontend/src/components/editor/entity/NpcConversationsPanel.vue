<script setup lang="ts">
/**
 * NpcConversationsPanel — how this NPC sees other NPCs, whether it joins NPC chatter, and the
 * topics it discusses with others while the protagonist can overhear them (/listen).
 */
import { computed } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import UiButton from '@/components/ui/UiButton.vue'
import UiDisclosure from '@/components/ui/UiDisclosure.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import { RELATION_KINDS, emptyRelation, emptyTopic, type ConversationTopic, type NpcRelation } from './npcConversationTypes'

const ef = useEntityFormContext()

const KIND_OPTIONS = RELATION_KINDS.map((kind) => ({ value: kind, label: kind.charAt(0) + kind.slice(1).toLowerCase() }))

const npcOptions = computed(() =>
  (ef.props.referenceOptions || [])
    .filter((entry) => entry.type === 'NPC' && entry.id.toUpperCase() !== String(ef.entityId || '').toUpperCase())
    .map((entry) => ({ value: entry.id, label: `${entry.name || entry.id} (${entry.id})` })),
)
const partnerOptions = computed(() => [{ value: '', label: 'Any other character present' }, ...npcOptions.value])

const relations = computed<NpcRelation[]>(() => ef.localForm.relations as NpcRelation[])
const topics = computed<ConversationTopic[]>(() => ef.localForm.conversation_topics as ConversationTopic[])

function addRelation(): void {
  ef.localForm.relations = [...relations.value, emptyRelation()]
}

function removeRelation(index: number): void {
  ef.localForm.relations = relations.value.filter((_, i) => i !== index)
}

function addTopic(): void {
  ef.localForm.conversation_topics = [...topics.value, emptyTopic()]
}

function removeTopic(index: number): void {
  ef.localForm.conversation_topics = topics.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div class="space-y-6">
    <UiToggle
      v-model="ef.localForm.chatty"
      label="Takes part in NPC chatter"
      description="Off keeps this character out of the conversations NPCs start on their own (e.g. a guard on duty). It still answers when spoken to."
    />

    <UiField
      label="Relations"
      hint="How this character sees other characters. Present characters talk to each other accordingly."
      info="Relations are one-sided: Bram can call Mara a friend while she sees a rival. Friends, family, partners, allies, colleagues, superiors and subordinates also pass on what they remember about the protagonist when the adventure enables gossip."
    >
      <div class="space-y-3">
        <div v-for="(relation, index) in relations" :key="`rel-${index}`" class="grid grid-cols-1 gap-2 md:grid-cols-[1fr_10rem_1fr_auto]">
          <UiSelect v-model="relation.npc_id" :options="npcOptions" placeholder="Character…" />
          <UiSelect v-model="relation.kind" :options="KIND_OPTIONS" />
          <UiInput v-model="relation.note" maxlength="80" placeholder="Reason (optional), e.g. owes her money" />
          <UiIconButton :icon="Trash2" label="Remove relation" variant="danger" @click="removeRelation(index)" />
        </div>
        <UiButton size="sm" :icon="Plus" @click="addRelation">Add relation</UiButton>
      </div>
    </UiField>

    <UiField
      label="Conversation topics"
      hint="Topics this character discusses with another character while the protagonist can overhear them."
      info="When NPC chatter starts a conversation, or the player uses /listen, an open topic of a present character comes up first. It counts as heard once it is narrated: 'On heard' runs, scripts with the On Conversation Heard trigger fire and the clue is kept as a world memory."
    >
      <div class="space-y-4">
        <div v-for="(topic, index) in topics" :key="`topic-${index}`" class="space-y-3 rounded-xl border border-wb-line p-4">
          <div class="flex items-start gap-2">
            <UiInput v-model="topic.topic" class="flex-1" maxlength="160" placeholder="What they talk about, e.g. the cellar door left open at night" />
            <UiIconButton :icon="Trash2" label="Remove topic" variant="danger" @click="removeTopic(index)" />
          </div>
          <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
            <UiField label="With">
              <UiSelect v-model="topic.with_npc_id" :options="partnerOptions" />
            </UiField>
            <UiField label="Topic id" hint="Target of On Conversation Heard scripts.">
              <UiInput v-model="topic.id" mono placeholder="e.g. cellar_door" />
            </UiField>
          </div>
          <UiField label="Clue the listener must learn" hint="Leave empty for flavor talk.">
            <UiInput v-model="topic.must_convey" maxlength="160" placeholder="e.g. the cellar door is unlocked after midnight" />
          </UiField>
          <UiToggle v-model="topic.repeatable" label="Repeatable" description="Can come up again after it was heard." />
          <UiDisclosure label="Scripts & triggers">
            <div class="space-y-3 pt-2">
              <UiField label="Guard" hint="Python condition; the topic only comes up while it is True.">
                <UiInput v-model="topic.guard_expression" mono placeholder="e.g. tw.flags.get('met_captain')" />
              </UiField>
              <UiField label="On heard (script)">
                <UiTextarea v-model="topic.on_heard_script" :rows="2" mono placeholder="tw.flags.set('knows_cellar', True)" />
              </UiField>
              <UiField label="On heard (system note)">
                <UiInput v-model="topic.on_heard_text" placeholder="e.g. You now know when the cellar is open." />
              </UiField>
            </div>
          </UiDisclosure>
        </div>
        <UiButton size="sm" :icon="Plus" @click="addTopic">Add topic</UiButton>
      </div>
    </UiField>
  </div>
</template>
