<script setup lang="ts">
/**
 * StoryTabPanel — Content of the non-story tabs (Passages, Discoveries, System log).
 */
import type { ChatMessage } from '@/types'
import PassagesPanel from './PassagesPanel.vue'
import DiscoveriesPanel from './DiscoveriesPanel.vue'
import SystemLogPanel from './SystemLogPanel.vue'
import type { StoryTabId } from './types'
import type { TurnError } from '../systemMessages'

const props = defineProps<{
  tab: Exclude<StoryTabId, 'story'>
  sceneExits: any[]
  items: any[]
  systemMessages: ChatMessage[]
  systemSeenCount: number
  currentSceneName?: string | null
  isEvaluating?: boolean
  turnError?: TurnError
}>()

const emit = defineEmits<{
  traverseExit: [exit: any]
  itemClick: [item: any]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  itemContextmenu: [item: any, event: MouseEvent]
  takeDirect: [item: any]
}>()
</script>

<template>
  <div role="tabpanel" class="tw-panel flex-1 min-h-0 overflow-y-auto tw-scroll p-3 sm:p-5">
    <PassagesPanel
      v-if="props.tab === 'passages'"
      :scene-exits="props.sceneExits"
      :current-scene-name="props.currentSceneName"
      :is-evaluating="props.isEvaluating"
      @traverse-exit="(exit) => emit('traverseExit', exit)"
    />
    <DiscoveriesPanel
      v-else-if="props.tab === 'discoveries'"
      :items="props.items"
      :is-evaluating="props.isEvaluating"
      @item-click="(item) => emit('itemClick', item)"
      @item-hover="(item, event) => emit('itemHover', item, event)"
      @item-leave="emit('itemLeave')"
      @item-contextmenu="(item, event) => emit('itemContextmenu', item, event)"
      @take-direct="(item) => emit('takeDirect', item)"
    />
    <SystemLogPanel
      v-else
      :messages="props.systemMessages"
      :seen-count="props.systemSeenCount"
      :turn-error="props.turnError"
    />
  </div>
</template>
