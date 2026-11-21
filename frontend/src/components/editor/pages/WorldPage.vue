<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import OverviewCreditsCard from '@/components/editor/overview/OverviewCreditsCard.vue'
import OverviewDetailsCard from '@/components/editor/overview/OverviewDetailsCard.vue'
import OverviewOutcomeCard from '@/components/editor/overview/OverviewOutcomeCard.vue'
import OverviewStoryCard from '@/components/editor/overview/OverviewStoryCard.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiTabs from '@/components/ui/UiTabs.vue'

/** Overview: the adventure's core settings (tab in `?panel=`). Changes are saved through the editor's save bar. */
const route = useRoute()
const router = useRouter()

type PanelId = 'general' | 'story' | 'credits' | 'outcome'

const TABS: { id: PanelId; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'story', label: 'Story' },
  { id: 'credits', label: 'Credits' },
  { id: 'outcome', label: 'Outcome' },
]

const PANEL_IDS = new Set<string>(TABS.map((tab) => tab.id))

const panel = computed<PanelId>({
  get: () => {
    const value = route.query.panel
    return typeof value === 'string' && PANEL_IDS.has(value) ? (value as PanelId) : 'general'
  },
  set: (value) => {
    void router.replace({ query: { ...route.query, panel: value === 'general' ? undefined : value } })
  },
})
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Overview" description="Title, play style, story and how the adventure is won or lost." />
    <UiTabs v-model="panel" :tabs="TABS" label="Overview sections" />
    <div v-show="panel === 'general'">
      <OverviewDetailsCard />
    </div>
    <div v-show="panel === 'story'">
      <OverviewStoryCard />
    </div>
    <div v-show="panel === 'credits'">
      <OverviewCreditsCard />
    </div>
    <div v-show="panel === 'outcome'">
      <OverviewOutcomeCard />
    </div>
  </div>
</template>
