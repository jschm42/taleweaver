<script setup lang="ts">
/**
 * SheetHeroPanel — Hero tab of the character sheet: a poster-style stage with the portrait
 * filling the tab and the name and biography laid over it. The backstory reuses the skin's
 * narration box (drop cap, paper, fonts).
 */
import { computed } from 'vue'
import type { CharacterSheet } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import { useBrokenImages } from './sheetItems'
import { vDropCap } from '@/skins/vDropCap'

const props = defineProps<{
  sheet: CharacterSheet
}>()

const { showImage, handleImageError } = useBrokenImages()

const portraitUrl = computed(() =>
  showImage(props.sheet.profile_image) ? getImageUrl(props.sheet.profile_image) : null
)
</script>

<template>
  <div class="tw-hero-stage h-full min-h-[26rem]">
    <!-- Ambient backdrop: a blurred copy of the portrait fills the free space -->
    <img v-if="portraitUrl" :src="portraitUrl" alt="" aria-hidden="true" class="tw-hero-ambient" />

    <!-- Portrait (full height, fades into the backdrop) -->
    <figure class="tw-hero-portrait">
      <img
        v-if="portraitUrl"
        :src="portraitUrl"
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

    <!-- Identity & Biography, laid over the portrait -->
    <div class="tw-hero-copy tw-dialog-scroll">
      <div class="mt-auto flex flex-col gap-4">
        <div class="tw-hero-identity">
          <h4 class="tw-dialog-title text-3xl sm:text-4xl">{{ props.sheet.name || 'Unnamed' }}</h4>
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
  </div>
</template>
