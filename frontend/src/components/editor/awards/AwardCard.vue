<script setup lang="ts">
import { Pencil, ShieldCheck, Trash2 } from 'lucide-vue-next'
import { hasHardRules, type Award } from '@/composables/editor/useAwards'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import bronzeTrophy from '@/assets/svg/bronze-award-trophy.svg'
import silverTrophy from '@/assets/svg/silver-award-trophy.svg'
import goldTrophy from '@/assets/svg/gold-award-trophy.svg'

/** One award: trophy, title, tier, description and how it is granted. */
defineProps<{ award: Award; busy: boolean }>()

const emit = defineEmits<{ edit: []; remove: [] }>()

const TROPHIES: Record<string, string> = { gold: goldTrophy, silver: silverTrophy, bronze: bronzeTrophy }

function trophy(tier: string): string {
  return TROPHIES[String(tier || '').toLowerCase()] ?? bronzeTrophy
}
</script>

<template>
  <article class="flex flex-col gap-3 rounded-xl border border-wb-line bg-wb-surface p-4 transition-colors hover:border-wb-line-strong">
    <div class="flex items-start gap-3">
      <img :src="trophy(award.tier)" :alt="`${award.tier || 'bronze'} trophy`" class="h-10 w-10 shrink-0 object-contain" />
      <div class="min-w-0 flex-1 space-y-1">
        <button
          type="button"
          class="wb-subheading rounded-md text-left hover:text-wb-accent-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
          @click="emit('edit')"
        >
          {{ award.title || 'Untitled award' }}
        </button>
        <div class="flex flex-wrap items-center gap-1.5">
          <UiBadge class="capitalize">{{ award.tier || 'bronze' }}</UiBadge>
          <span class="wb-mono text-wb-faint">{{ award.key }}</span>
        </div>
      </div>
    </div>
    <p class="wb-body line-clamp-2 text-wb-muted">{{ award.description }}</p>
    <p v-if="award.requirement" class="wb-hint line-clamp-2"><span class="text-wb-body">Granted when:</span> {{ award.requirement }}</p>
    <div class="mt-auto flex items-center justify-between gap-2 border-t border-wb-line pt-3">
      <UiBadge v-if="hasHardRules(award)" tone="info">
        <ShieldCheck class="h-3 w-3" aria-hidden="true" />
        Engine-checked
      </UiBadge>
      <span v-else class="wb-hint">Judged by the Game Master</span>
      <div class="flex gap-0.5">
        <UiIconButton :icon="Pencil" label="Edit award" size="sm" :disabled="busy" @click="emit('edit')" />
        <UiIconButton :icon="Trash2" label="Delete award" size="sm" variant="danger" :disabled="busy" @click="emit('remove')" />
      </div>
    </div>
  </article>
</template>
