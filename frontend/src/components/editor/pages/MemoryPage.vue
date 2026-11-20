<script setup lang="ts">
import OverviewMemoryCard from '@/components/editor/overview/OverviewMemoryCard.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'

/** Memory: how much of the story the narration model remembers. Saved through the editor's save bar. */
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Memory" description="How much of the past story the narrator keeps in mind." />
    <OverviewMemoryCard />
  </div>
</template>
