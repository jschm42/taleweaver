<script setup lang="ts">
/**
 * DebugNpcSocialPanel — NPC memory and conversation data on a debug NPC card: the stored facts
 * (key = text, used / slots), relations (script changes marked), chatter opt-out and the
 * conversation topics with their heard state.
 */
import { computed } from 'vue'
import { Brain, MessagesSquare, Megaphone } from 'lucide-vue-next'
import type { DebugNpcSocial } from './debugNpcSocialTypes'

const props = defineProps<{ npc: DebugNpcSocial }>()

const memory = computed(() => props.npc.memory ?? { slots: 0, facts: [] })
const conversations = computed(() => props.npc.conversations ?? { chatty: true, relations: [], topics: [] })
const gossip = computed(() => props.npc.gossip ?? { told: [], heard: [] })
const hasGossip = computed(() => gossip.value.told.length > 0 || gossip.value.heard.length > 0)
const hasConversationData = computed(
  () => !conversations.value.chatty || conversations.value.relations.length > 0 || conversations.value.topics.length > 0,
)
</script>

<template>
  <div class="space-y-2">
    <div
      v-if="memory.slots > 0 || memory.facts.length"
      class="bg-teal-950/30 border border-teal-500/30 rounded-xl p-2.5 space-y-1 text-[11px] font-mono leading-snug break-words"
    >
      <div class="flex items-center justify-between text-[9px] font-black uppercase tracking-wider text-teal-400">
        <span class="flex items-center gap-1"><Brain class="w-3 h-3" /> NPC Memory</span>
        <span>{{ memory.facts.length }} / {{ memory.slots }}</span>
      </div>
      <p v-if="!memory.facts.length" class="text-teal-200/60 italic">Nothing remembered yet.</p>
      <p v-for="fact in memory.facts" :key="fact.key" :class="fact.hearsay ? 'text-orange-200/90' : 'text-teal-200/90'">
        <span
          v-if="fact.hearsay"
          class="mr-1 px-1 rounded text-[9px] font-black uppercase bg-orange-500/20 text-orange-300"
        >gossip</span>
        <span class="font-bold" :class="fact.hearsay ? 'text-orange-300' : 'text-teal-400'">{{ fact.key }}:</span> {{ fact.text }}
      </p>
    </div>

    <div
      v-if="hasGossip"
      class="bg-orange-950/30 border border-orange-500/30 rounded-xl p-2.5 space-y-1 text-[11px] font-mono leading-snug break-words"
    >
      <div class="flex items-center gap-1 text-[9px] font-black uppercase tracking-wider text-orange-400">
        <Megaphone class="w-3 h-3" /> Gossip
      </div>
      <p v-for="(entry, idx) in gossip.heard" :key="`h-${idx}`" class="text-orange-200/90">
        heard <span class="text-orange-300 font-bold">{{ entry.key }}</span> from {{ entry.from }}
      </p>
      <p v-for="(entry, idx) in gossip.told" :key="`t-${idx}`" class="text-orange-200/90">
        told {{ entry.to }} about <span class="text-orange-300 font-bold">{{ entry.key }}</span>
      </p>
    </div>

    <div
      v-if="hasConversationData"
      class="bg-sky-950/30 border border-sky-500/30 rounded-xl p-2.5 space-y-1.5 text-[11px] font-mono leading-snug break-words"
    >
      <div class="flex items-center justify-between text-[9px] font-black uppercase tracking-wider text-sky-400">
        <span class="flex items-center gap-1"><MessagesSquare class="w-3 h-3" /> Conversations</span>
        <span v-if="!conversations.chatty" class="text-amber-300">No chatter</span>
      </div>
      <p v-for="rel in conversations.relations" :key="rel.npc_id" class="text-sky-200/90">
        <span class="text-sky-400 font-bold">{{ rel.kind.toLowerCase() }}</span> of {{ rel.name }}
        <span v-if="rel.note" class="text-sky-200/60">({{ rel.note }})</span>
        <span v-if="rel.changed_by_script" class="ml-1 text-amber-300">[script]</span>
      </p>
      <div v-for="topic in conversations.topics" :key="topic.id" class="pt-1 border-t border-sky-500/20">
        <p class="text-sky-200/90">
          <span
            class="mr-1 px-1 rounded text-[9px] font-black uppercase"
            :class="topic.heard ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400'"
          >{{ topic.heard ? 'heard' : 'open' }}</span>
          <span class="text-sky-400 font-bold">{{ topic.id }}</span>: {{ topic.topic }}
        </p>
        <p v-if="topic.with_npc_id" class="text-sky-200/60">with {{ topic.with_npc_id }}<span v-if="topic.repeatable"> · repeatable</span></p>
        <p v-if="topic.must_convey" class="text-sky-200/60">clue: {{ topic.must_convey }}</p>
        <p v-if="topic.guard_expression" class="text-sky-200/60">guard: {{ topic.guard_expression }}</p>
      </div>
    </div>
  </div>
</template>
