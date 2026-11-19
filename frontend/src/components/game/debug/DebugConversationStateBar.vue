<script setup lang="ts">
/**
 * DebugConversationStateBar — session-wide NPC conversation state above the debug NPC grid:
 * chatter level and player switch, gossip, the quiet-message counter, the last pair, heard
 * topics and a conversation direction still waiting for the next narration.
 */
import { computed } from 'vue'
import { MessagesSquare } from 'lucide-vue-next'
import type { DebugConversationSession } from './debugNpcSocialTypes'

const props = defineProps<{ state: DebugConversationSession }>()

// Newest gossip first; the backend keeps the last 30.
const gossipLog = computed(() => [...(props.state.gossip_log ?? [])].reverse())
</script>

<template>
  <div class="mb-4 shrink-0 rounded-2xl border border-sky-500/30 bg-sky-950/20 p-3 text-[11px] font-mono text-sky-200/90 space-y-1">
    <div class="flex flex-wrap items-center gap-x-4 gap-y-1">
      <span class="flex items-center gap-1 text-[9px] font-black uppercase tracking-wider text-sky-400">
        <MessagesSquare class="w-3 h-3" /> NPC Conversations
      </span>
      <span>chatter: <strong class="text-white">{{ state.chatter }}</strong></span>
      <span>player switch: <strong :class="state.player_enabled ? 'text-emerald-300' : 'text-amber-300'">{{ state.player_enabled ? 'on' : 'off' }}</strong></span>
      <span>gossip: <strong class="text-white">{{ state.gossip ? 'on' : 'off' }}</strong></span>
      <span>quiet messages: <strong class="text-white">{{ state.quiet }}</strong><span v-if="state.scene" class="text-sky-200/60"> in {{ state.scene }}</span></span>
      <span v-if="state.last_pair.length">last pair: <strong class="text-white">{{ state.last_pair.join(' + ') }}</strong></span>
    </div>
    <div v-if="state.heard.length">heard topics: {{ state.heard.join(', ') }}</div>
    <div v-if="!state.gossip" class="text-sky-200/60">
      Gossip is off in this session's copy of the adventure (sessions keep the settings they started with).
    </div>
    <details v-else class="text-orange-200/90">
      <summary class="cursor-pointer">gossip log ({{ gossipLog.length }})</summary>
      <p v-if="!gossipLog.length" class="text-sky-200/60 pl-3">
        Nothing passed on yet. Gossip runs when the scene or chapter changes, between memory characters with a friendly relation in the same place.
      </p>
      <p v-for="(entry, idx) in gossipLog" :key="idx" class="pl-3">
        {{ entry.teller }} → {{ entry.listener }}: <strong>{{ entry.key }}</strong>
        <span class="text-sky-200/60">({{ entry.scene_id }}, minute {{ entry.minute }})</span>
      </p>
    </details>
    <div v-if="state.pending_beat" class="text-amber-200/90">pending: {{ state.pending_beat }}</div>
  </div>
</template>
