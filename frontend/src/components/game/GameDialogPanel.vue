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
  inputLocked?: boolean
  exp: number
  mode?: 'rpg' | 'story' | 'chat'
  inventoryGlow?: boolean
  mapGlow?: boolean
  questGlow?: boolean
  activeActionId?: string | null
  sheet?: any
  gameId?: string
  currentSceneDescription?: string
}>()

const emit = defineEmits<{
  send: [content: string]
  openSheet: []
  openMap: []
  openQuests: []
  npcHover: [name: string, event: MouseEvent]
  npcLeave: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  openDebug: []
  toggleDebugLog: [enabled: boolean]
  takeDirect: [entity: any]
  npcContextmenu: [entity: any, event: MouseEvent]
  itemContextmenu: [entity: any, event: MouseEvent]
  selectAction: [actionId: string | null]
  npcClick: [name: string]
  itemClick: [item: any]
}>()

const chatWindow = ref<any>(null)

function appendText(text: string) {
  chatWindow.value?.appendText(text)
}

defineExpose({ appendText })
</script>

<template>
  <div class="flex-grow relative overflow-hidden flex flex-col items-stretch px-4 pb-4 sm:px-6 sm:pb-6 pt-2 w-full mx-auto min-h-0">
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
      :inventory-glow="props.inventoryGlow"
      :map-glow="props.mapGlow"
      :quest-glow="props.questGlow"
      :active-action-id="props.activeActionId"
      :mode="props.mode"
      :input-locked="props.inputLocked"
      :sheet="props.sheet"
      :game-id="props.gameId"
      :current-scene-description="props.currentSceneDescription"
      @send="emit('send', $event)"
      @open-sheet="emit('openSheet')"
      @open-map="emit('openMap')"
      @open-quests="emit('openQuests')"
      @npc-hover="(name, event) => emit('npcHover', name, event)"
      @npc-leave="emit('npcLeave')"
      @item-hover="(item, event) => emit('itemHover', item, event)"
      @item-leave="emit('itemLeave')"
      @open-debug="emit('openDebug')"
      @take-direct="emit('takeDirect', $event)"
      @npc-contextmenu="(entity, event) => emit('npcContextmenu', entity, event)"
      @item-contextmenu="(entity, event) => emit('itemContextmenu', entity, event)"
      @select-action="emit('selectAction', $event)"
      @npc-click="emit('npcClick', $event)"
      @item-click="emit('itemClick', $event)"
    />

    <div v-if="props.mode !== 'chat'" class="absolute bottom-6 right-10 z-20 pointer-events-none animate-fade-in">
      <span class="text-xl font-black text-slate-300/60 uppercase tracking-[0.2em] tabular-nums">
        {{ props.exp }} XP
      </span>
    </div>
  </div>
</template>

