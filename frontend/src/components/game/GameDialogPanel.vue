<script setup lang="ts">
import { ref } from 'vue'
import ChatWindow from '@/components/game/ChatWindow.vue'
import type { ChatMessage } from '@/types'
import type { ConnectionStatus } from '@/composables/useGameSocket'

const props = defineProps<{
  messages: ChatMessage[]
  status: ConnectionStatus
  npcMetadata: Record<string, any>
  entities: any[]
  inventoryItems: any[]
  trackedQuest?: any
  statusText?: string
  showDebugLog: boolean
  debugLogs: { timestamp: string, content: string }[]
  gameOverReason?: string | null
  exp: number
}>()

const emit = defineEmits<{
  send: [content: string]
  openSheet: []
  openMap: []
  openQuests: []
  openWalkthrough: []
  npcHover: [name: string, event: MouseEvent]
  npcLeave: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  openDebug: []
  toggleDebugLog: [enabled: boolean]
}>()

const chatWindow = ref<any>(null)

function appendText(text: string) {
  chatWindow.value?.appendText(text)
}

defineExpose({ appendText })
</script>

<template>
  <div class="flex-grow relative overflow-hidden flex flex-col items-stretch px-4 pb-4 sm:px-6 sm:pb-6 pt-2 w-full mx-auto min-h-0">
    <div v-if="props.gameOverReason" class="w-full bg-red-900/20 border border-red-500/30 p-4 rounded-xl mb-4 text-red-400 font-medium flex items-center gap-3 shadow-lg backdrop-blur-sm shrink-0">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <span>{{ props.gameOverReason }}</span>
    </div>

    <ChatWindow
      ref="chatWindow"
      :messages="props.messages"
      :status="props.status"
      :npc-metadata="props.npcMetadata"
      :entities="props.entities"
      :inventory="props.inventoryItems"
      :tracked-quest="props.trackedQuest"
      :status-text="props.statusText"
      :show-debug-log="props.showDebugLog"
      :debug-logs="props.debugLogs"
      @send="emit('send', $event)"
      @open-sheet="emit('openSheet')"
      @open-map="emit('openMap')"
      @open-quests="emit('openQuests')"
      @open-walkthrough="emit('openWalkthrough')"
      @npc-hover="(name, event) => emit('npcHover', name, event)"
      @npc-leave="emit('npcLeave')"
      @item-hover="(item, event) => emit('itemHover', item, event)"
      @item-leave="emit('itemLeave')"
      @open-debug="emit('openDebug')"
      @toggle-debug-log="emit('toggleDebugLog', $event)"
    />

    <div class="absolute bottom-6 right-10 z-20 pointer-events-none animate-fade-in">
      <span class="text-sm font-black text-slate-300/60 uppercase tracking-[0.2em] tabular-nums">
        {{ props.exp }} XP
      </span>
    </div>
  </div>
</template>
