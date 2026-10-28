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
    class="w-72 2xl:w-80 shrink-0 flex flex-col gap-2 min-h-0 overflow-y-auto tw-scroll"
    aria-label="Scene"
  >
    <section v-if="props.sceneSwitches.length > 0" class="tw-panel flex flex-col gap-2 p-2.5">
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

    <section v-if="props.sceneExits.length > 0" class="tw-panel p-2.5">
      <PassagesPanel
        compact
        :scene-exits="props.sceneExits"
        :current-scene-name="props.currentSceneName"
        :is-evaluating="props.isEvaluating"
        @traverse-exit="(exit) => emit('traverseExit', exit)"
      />
    </section>

    <section v-if="props.items.length > 0" class="tw-panel p-2.5">
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
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
