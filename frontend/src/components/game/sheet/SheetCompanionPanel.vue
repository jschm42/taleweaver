<script setup lang="ts">
/**
 * SheetCompanionPanel — The companion's profile page of the hero dialog: portrait and
 * description like the hero tab, plus where the companion is, its party settings, its
 * attributes and the orders "Stay here" / "Follow me".
 */
import { computed } from 'vue'
import type { CompanionSheet } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import { useBrokenImages } from './sheetItems'
import { vDropCap } from '@/skins/vDropCap'

const props = defineProps<{
  companion: CompanionSheet
}>()

const emit = defineEmits<{
  command: [cmd: string]
}>()

const { showImage, handleImageError } = useBrokenImages()

const portraitUrl = computed(() =>
  showImage(props.companion.image_url) ? getImageUrl(props.companion.image_url) : null
)

const ATTRIBUTES: Array<{ key: string; label: string }> = [
  { key: 'strength', label: 'STR' },
  { key: 'dexterity', label: 'DEX' },
  { key: 'intelligence', label: 'INT' },
  { key: 'wisdom', label: 'WIS' },
  { key: 'charisma', label: 'CHA' },
  { key: 'armor_class', label: 'AC' },
]

const attributes = computed(() =>
  ATTRIBUTES.map((attr) => ({ ...attr, value: props.companion.stats?.[attr.key] ?? '–' }))
)

const whereabouts = computed((): string => {
  if (props.companion.is_defeated) return 'Downed'
  if (!props.companion.present) return 'Waits elsewhere'
  return props.companion.following ? 'At your side, follows you' : 'Waits here'
})

const titleCase = (value: string): string => value.charAt(0) + value.slice(1).toLowerCase()

/** Orders reach the companion only when it stands next to the protagonist. */
const canOrder = computed(() => props.companion.present && !props.companion.is_defeated)
</script>

<template>
  <div class="tw-hero-stage h-full min-h-[26rem]">
    <img v-if="portraitUrl" :src="portraitUrl" alt="" aria-hidden="true" class="tw-hero-ambient" />

    <figure class="tw-hero-portrait">
      <img
        v-if="portraitUrl"
        :src="portraitUrl"
        :alt="props.companion.name"
        class="w-full h-full object-cover object-top"
        @error="handleImageError(props.companion.image_url)"
      />
      <div v-else class="w-full h-full flex items-center justify-center">
        <img
          src="@/assets/svg/upper-body-bust-silhouette.svg"
          alt=""
          class="tw-dialog-silhouette w-2/3 h-2/3 object-contain"
        />
      </div>
    </figure>

    <div class="tw-hero-copy tw-dialog-scroll">
      <div class="mt-auto flex flex-col gap-4">
        <div class="tw-hero-identity">
          <h4 class="tw-dialog-title text-3xl sm:text-4xl">{{ props.companion.name }}</h4>
          <div class="tw-dialog-eyebrow text-xs sm:text-sm mt-1">Companion · {{ whereabouts }}</div>
          <div class="tw-muted text-xs mt-1.5">
            Tactics: <span class="font-semibold">{{ titleCase(props.companion.tactics) }}</span>
            · Banter: <span class="font-semibold">{{ titleCase(props.companion.banter) }}</span>
          </div>
        </div>

        <div class="grid grid-cols-6 gap-1.5 sm:gap-2">
          <div v-for="attr in attributes" :key="attr.key" class="tw-card flex flex-col items-center py-1.5">
            <span class="tw-muted text-[10px] font-black tracking-widest">{{ attr.label }}</span>
            <span class="tw-dialog-title text-base sm:text-lg">{{ attr.value }}</span>
          </div>
        </div>

        <div v-if="canOrder" class="flex flex-wrap gap-2">
          <button
            v-if="props.companion.following"
            type="button"
            class="tw-tab"
            title="The companion stays in this scene until you call it back."
            @click="emit('command', '/companion wait')"
          >
            Stay here
          </button>
          <button
            v-else
            type="button"
            class="tw-tab"
            title="The companion follows you through exits again."
            @click="emit('command', '/companion follow')"
          >
            Follow me
          </button>
        </div>

        <section class="tw-narration">
          <div class="tw-narration-label">About</div>
          <p v-drop-cap class="tw-narration-text tw-dialog-bio">
            {{ props.companion.description || 'Your loyal travel companion.' }}
          </p>
        </section>
      </div>
    </div>
  </div>
</template>
