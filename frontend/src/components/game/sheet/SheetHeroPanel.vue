<script setup lang="ts">
/**
 * SheetHeroPanel — Hero tab of the character sheet: full portrait and biography.
 * The backstory reuses the skin's narration box (drop cap, paper, fonts).
 */
import type { CharacterSheet } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import { useBrokenImages } from './sheetItems'
import { vDropCap } from '@/skins/vDropCap'

const props = defineProps<{
  sheet: CharacterSheet
}>()

const { showImage, handleImageError } = useBrokenImages()
</script>

<template>
  <div class="flex flex-col sm:flex-row gap-5 sm:gap-7 items-center sm:items-start">
    <!-- Portrait -->
    <figure class="tw-dialog-portrait shrink-0 w-48 sm:w-56 md:w-64 aspect-[2/3]">
      <img
        v-if="showImage(props.sheet.profile_image)"
        :src="getImageUrl(props.sheet.profile_image)"
        :alt="props.sheet.name || 'Hero portrait'"
        class="w-full h-full object-cover object-top"
        @error="handleImageError(props.sheet.profile_image)"
      />
      <div v-else class="w-full h-full flex items-center justify-center">
        <img
          src="@/assets/svg/upper-body-bust-silhouette.svg"
          alt=""
          class="tw-dialog-silhouette w-2/3 h-2/3 object-contain"
        />
      </div>
    </figure>

    <!-- Identity & Biography -->
    <div class="flex-1 min-w-0 w-full flex flex-col gap-4">
      <div class="text-center sm:text-left">
        <h4 class="tw-dialog-title text-2xl sm:text-3xl">{{ props.sheet.name || 'Unnamed' }}</h4>
        <div class="tw-dialog-eyebrow text-xs sm:text-sm mt-1">{{ props.sheet.role || 'Adventurer' }}</div>
        <div v-if="props.sheet.adventure_title" class="tw-muted text-xs mt-1.5">
          Adventure: <span class="font-semibold">{{ props.sheet.adventure_title }}</span>
        </div>
      </div>

      <section class="tw-narration">
        <div class="tw-narration-label">Backstory</div>
        <p v-drop-cap class="tw-narration-text tw-dialog-bio">
          {{ props.sheet.description || 'No detailed biography or historical records found for this adventurer.' }}
        </p>
      </section>
    </div>
  </div>
</template>
