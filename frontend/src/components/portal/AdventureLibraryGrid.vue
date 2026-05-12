<script setup lang="ts">
import type { AdventureTemplateSummary } from '@/types'
import PortalCreateAdventureCard from './PortalCreateAdventureCard.vue'
import ImportExamplesCard from './ImportExamplesCard.vue'
import PendingAdventureCard from './PendingAdventureCard.vue'
import AdventureTemplateCard from './AdventureTemplateCard.vue'

defineProps<{
  visibleTemplates: AdventureTemplateSummary[]
  pendingCards: any[]
  isSeeding: boolean
  loadingWordIndex: number
}>()

defineEmits<{
  (e: 'create'): void
  (e: 'import-samples'): void
  (e: 'remove-failed-pending', adventureId: string, kind: 'creation' | 'import'): void
  (e: 'cancel-pending', adventureId: string): void
  (e: 'start-session', templateId: string): void
  (e: 'edit', templateId: string): void
  (e: 'export-adz', templateId: string, title: string): void
  (e: 'export-adv', templateId: string, title: string): void
  (e: 'delete', templateId: string, title: string): void
  (e: 'dismiss-warning', templateId: string): void
}>()
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-6 gap-5 xl:gap-4">
    <PortalCreateAdventureCard @click="$emit('create')" />
    
    <ImportExamplesCard 
      v-if="!isSeeding" 
      @import="$emit('import-samples')" 
    />

    <!-- Loading indicator for seeding -->
    <div v-if="isSeeding" class="flex flex-col items-center justify-center border-2 border-dashed border-white/10 rounded-xl aspect-[3/2] bg-white/5 gap-3">
      <div class="w-8 h-8 border-2 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
      <span class="text-xxs text-aether-primary uppercase tracking-widest font-bold">Importing Tales...</span>
    </div>

    <PendingAdventureCard
      v-for="pending in pendingCards"
      :key="`pending-${pending.adventureId}`"
      :pending="pending"
      :loading-word-index="loadingWordIndex"
      @remove-failed="(id, kind) => $emit('remove-failed-pending', id, kind)"
      @cancel="(id) => $emit('cancel-pending', id)"
    />

    <AdventureTemplateCard
      v-for="entry in visibleTemplates"
      :key="entry.template_id"
      :template="entry"
      @start-session="(id) => $emit('start-session', id)"
      @edit="(id) => $emit('edit', id)"
      @export-adz="(id, title) => $emit('export-adz', id, title)"
      @export-adv="(id, title) => $emit('export-adv', id, title)"
      @delete="(id, title) => $emit('delete', id, title)"
      @dismiss-warning="(id) => $emit('dismiss-warning', id)"
    />
  </div>
</template>
