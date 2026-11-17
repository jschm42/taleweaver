<script setup lang="ts">
import OverviewCreditsCard from '@/components/editor/overview/OverviewCreditsCard.vue'
import OverviewDetailsCard from '@/components/editor/overview/OverviewDetailsCard.vue'
import OverviewMemoryCard from '@/components/editor/overview/OverviewMemoryCard.vue'
import OverviewOutcomeCard from '@/components/editor/overview/OverviewOutcomeCard.vue'
import OverviewStoryCard from '@/components/editor/overview/OverviewStoryCard.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'

/** Overview: the adventure's core settings. Changes are saved through the editor's save bar. */
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Overview" description="Title, play style, story and how the adventure is won or lost." />
    <OverviewDetailsCard />
    <OverviewStoryCard />
    <OverviewOutcomeCard />
    <OverviewMemoryCard />
    <OverviewCreditsCard />
  </div>
</template>
