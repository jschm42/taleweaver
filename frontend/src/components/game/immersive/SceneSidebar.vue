<script setup lang="ts">
/**
 * SceneSidebar — Passages, Discoveries and scene switches as compact tile panels in a
 * right-hand column. Used on wide screens instead of the corresponding story tabs.
 */
import PassagesPanel from './tabs/PassagesPanel.vue'
import DiscoveriesPanel from './tabs/DiscoveriesPanel.vue'
import { switchState } from './switchState'

const props = defineProps<{
  sceneExits: any[]
  items: any[]
  sceneSwitches: any[]
  currentSceneName?: string | null
  isEvaluating?: boolean
}>()

const emit = defineEmits<{
  switchFlip: [entity: any]
  traverseExit: [exit: any]
  itemClick: [item: any]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  itemContextmenu: [item: any, event: MouseEvent]
  takeDirect: [item: any]
}>()
</script>

<template>
  <aside
    v-if="props.sceneExits.length > 0 || props.items.length > 0 || props.sceneSwitches.length > 0"
    class="w-72 2xl:w-80 shrink-0 flex flex-col gap-4 min-h-0 overflow-y-auto tw-scroll p-1.5"
    aria-label="Scene"
  >
    <section v-if="props.sceneSwitches.length > 0" class="tw-sidebar-group flex flex-col gap-2">
      <h3 class="tw-panel-title">Switches</h3>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="sw in props.sceneSwitches"
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
    </section>

    <section v-if="props.sceneExits.length > 0" class="tw-sidebar-group">
      <PassagesPanel
        compact
        :scene-exits="props.sceneExits"
        :current-scene-name="props.currentSceneName"
        :is-evaluating="props.isEvaluating"
        @traverse-exit="(exit) => emit('traverseExit', exit)"
      />
    </section>

    <section v-if="props.items.length > 0" class="tw-sidebar-group">
      <DiscoveriesPanel
        compact
        :items="props.items"
        :is-evaluating="props.isEvaluating"
        @item-click="(item) => emit('itemClick', item)"
        @item-hover="(item, event) => emit('itemHover', item, event)"
        @item-leave="emit('itemLeave')"
        @item-contextmenu="(item, event) => emit('itemContextmenu', item, event)"
        @take-direct="(item) => emit('takeDirect', item)"
      />
    </section>
  </aside>
</template>

<style scoped>
/* No panel background: the groups sit directly on the scene image (test layout). */
.tw-sidebar-group {
  color: var(--tw-panel-ink);
}

/* Without a panel behind them, headings and tiles need their own shadow to stay readable. */
.tw-sidebar-group :deep(.tw-panel-title),
.tw-sidebar-group :deep(.tw-muted) {
  text-shadow:
    0 1px 2px rgba(0, 0, 0, 0.95),
    0 0 10px rgba(0, 0, 0, 0.8);
}

.tw-sidebar-group :deep(.tw-card),
.tw-sidebar-group .tw-tab {
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.6),
    0 1px 3px rgba(0, 0, 0, 0.5);
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
