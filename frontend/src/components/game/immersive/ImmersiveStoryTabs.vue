<script setup lang="ts">
/**
 * ImmersiveStoryTabs — Tab bar framing the story area (Story, Passages, Discoveries, System)
 * plus quick toggles for the scene's switches. Styled by the active dialog skin.
 */
import { computed } from 'vue'
import { BookOpen, Compass, Sparkles, Terminal, Lock } from 'lucide-vue-next'
import type { StoryTabId } from './tabs/types'
import { switchState } from './switchState'

const activeTab = defineModel<StoryTabId>({ required: true })

const props = defineProps<{
  exitCount: number
  hasLockedExits: boolean
  itemCount: number
  unseenItems: number
  systemCount: number
  unseenSystem: number
  sceneSwitches: any[]
  isEvaluating?: boolean
  /** Passages, Discoveries and switches live in the scene sidebar: hide them here. */
  docked?: boolean
}>()

const emit = defineEmits<{
  switchFlip: [entity: any]
}>()

type TabEntry = { id: StoryTabId; label: string; count: number; unseen: number }

const tabs = computed<TabEntry[]>(() => {
  const entries: TabEntry[] = [
    { id: 'story', label: 'Story', count: 0, unseen: 0 },
    { id: 'passages', label: 'Passages', count: props.exitCount, unseen: 0 },
    { id: 'discoveries', label: 'Discoveries', count: props.itemCount, unseen: props.unseenItems },
    { id: 'system', label: 'System', count: props.systemCount, unseen: props.unseenSystem },
  ]
  const dockedIds: StoryTabId[] = props.docked ? ['passages', 'discoveries'] : []
  return entries.filter((tab) => tab.id === 'story' || (tab.count > 0 && !dockedIds.includes(tab.id)))
})

/** "Story" alone is not worth a tab bar: show tabs only when another section has entries. */
const hasSectionTabs = computed(() => tabs.value.length > 1)
const hasSwitches = computed(() => !props.docked && props.sceneSwitches.length > 0)
</script>

<template>
  <div
    v-if="hasSectionTabs || hasSwitches"
    class="relative z-30 shrink-0 mb-3 flex items-center gap-2 overflow-x-auto overflow-y-visible pt-1 pb-1 no-scrollbar"
  >
    <div v-if="hasSectionTabs" role="tablist" aria-label="Story sections" class="flex items-center gap-2">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.id"
        :aria-label="tab.unseen ? `${tab.label}, ${tab.unseen} new` : tab.label"
        class="tw-tab"
        :class="{ 'tw-tab--active': activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        <BookOpen v-if="tab.id === 'story'" class="w-4 h-4 shrink-0" />
        <Compass v-else-if="tab.id === 'passages'" class="w-4 h-4 shrink-0" />
        <Sparkles v-else-if="tab.id === 'discoveries'" class="w-4 h-4 shrink-0" />
        <Terminal v-else class="w-4 h-4 shrink-0" />
        <span :class="{ 'hidden sm:inline': tab.id !== 'story' }">{{ tab.label }}</span>
        <span v-if="tab.count" class="tw-tab-count">{{ tab.count }}</span>
        <Lock
          v-if="tab.id === 'passages' && props.hasLockedExits"
          class="w-3 h-3 shrink-0 text-red-400"
          aria-label="Contains a locked passage"
        />
        <span v-if="tab.unseen" class="tw-tab-dot" aria-hidden="true"></span>
      </button>
    </div>

    <!-- Scene switches (levers) -->
    <button
      v-for="sw in hasSwitches ? props.sceneSwitches : []"
      :key="sw.id"
      type="button"
      class="tw-tab shrink-0"
      :class="{ 'opacity-50 pointer-events-none': props.isEvaluating }"
      :title="`Toggle ${sw.name}`"
      @click="emit('switchFlip', sw)"
    >
      <i class="ra ra-lever text-sm"></i>
      <span class="truncate max-w-[8rem]">{{ sw.name }}</span>
      <span class="tw-tab-count">{{ switchState(sw) }}</span>
    </button>
  </div>
</template>

<style scoped>
.no-scrollbar {
  scrollbar-width: none;
}

.no-scrollbar::-webkit-scrollbar {
  display: none;
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
