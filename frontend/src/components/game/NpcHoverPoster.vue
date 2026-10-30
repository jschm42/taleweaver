<script setup lang="ts">
/**
 * NpcHoverPoster — Hover card for characters with a portrait: the 2:3 portrait fills the card
 * and name, vitals, possessions and description sit on a soft fade over its lower part.
 * The card keeps the portrait's 2:3 shape and shrinks with the space the tooltip gets.
 */
import StatBar from '@/components/game/StatBar.vue'
import { getImageUrl, getItemIcon } from '@/utils/game_icons'
import { formatEntityRefs } from '@/utils/entityRefs'

const props = defineProps<{
  entity: any
  ruleMode?: string | null
}>()

const emit = defineEmits<{
  (e: 'image-error'): void
}>()

const isDefeated = () => Boolean(props.entity.is_defeated || props.entity.hp === 0)
</script>

<template>
  <div class="npc-poster">
    <img
      :src="getImageUrl(props.entity.image_url)"
      :alt="props.entity.name"
      class="absolute inset-0 w-full h-full object-cover object-top"
      :class="{ 'grayscale opacity-60': isDefeated() }"
      @error="emit('image-error')"
    />
    <div class="npc-poster-fade" aria-hidden="true"></div>

    <div
      v-if="isDefeated()"
      class="absolute -right-8 top-4 bg-red-600 text-white text-[10px] font-black uppercase tracking-[0.12em] py-1 w-28 text-center rotate-45 shadow-lg z-20"
    >
      Defeated
    </div>

    <div class="npc-poster-copy">
      <div class="mt-auto flex flex-col gap-2.5">
        <div class="npc-poster-shadow">
          <div class="text-base font-black text-white uppercase tracking-wider leading-tight">{{ props.entity.name }}</div>
          <div v-if="props.entity.role" class="text-[11px] font-bold uppercase tracking-[0.16em] text-amber-300/90 mt-0.5">
            {{ props.entity.role }}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-x-3 gap-y-1">
          <StatBar v-if="props.entity.hp != null" label="HP" :value="Number(props.entity.hp)" :max="Number(props.entity.max_hp || 100)" color="crimson" size="sm" />
          <StatBar v-if="props.entity.stamina != null" label="STA" :value="Number(props.entity.stamina)" :max="Number(props.entity.max_stamina || 100)" color="emerald" size="sm" />
          <StatBar v-if="props.entity.mana != null && props.ruleMode === 'rpg'" label="MP" :value="Number(props.entity.mana)" :max="Number(props.entity.max_mana || 100)" color="sapphire" size="sm" />
        </div>

        <div v-if="Array.isArray(props.entity.inventory) && props.entity.inventory.length > 0" class="flex flex-wrap gap-1">
          <div
            v-for="(item, iidx) in props.entity.inventory.slice(0, 4)"
            :key="item?.id || iidx"
            class="px-1.5 py-0.5 rounded bg-slate-950/70 border border-slate-700/70 text-xxs text-slate-200 flex items-center gap-1"
          >
            <i :class="['ra text-[10px]', getItemIcon(typeof item === 'object' ? item?.item_type || 'PICKABLE' : 'PICKABLE'), 'text-amber-500/70']"></i>
            {{ typeof item === 'object' ? item?.name : item }}
          </div>
          <div v-if="props.entity.inventory.length > 4" class="text-xxs text-slate-400 self-center">+{{ props.entity.inventory.length - 4 }}</div>
        </div>

        <p
          v-if="props.entity.description"
          class="npc-poster-shadow text-xs text-slate-200 leading-relaxed italic whitespace-pre-wrap break-words"
          v-html="formatEntityRefs(props.entity.description)"
        ></p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.npc-poster {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 3;
  max-height: inherit;
  overflow: hidden;
}

/* Long, eased fade: the face stays clear, the lower half turns into a calm reading surface. */
.npc-poster-fade {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(
      to top,
      rgba(15, 23, 42, 0.98) 0%,
      rgba(15, 23, 42, 0.94) 22%,
      rgba(15, 23, 42, 0.8) 36%,
      rgba(15, 23, 42, 0.55) 47%,
      rgba(15, 23, 42, 0.28) 57%,
      rgba(15, 23, 42, 0.1) 66%,
      rgba(15, 23, 42, 0) 74%
    ),
    linear-gradient(to bottom, rgba(2, 6, 23, 0.35) 0%, rgba(2, 6, 23, 0) 18%);
}

.npc-poster-copy {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 0.75rem;
  scrollbar-width: none;
}

.npc-poster-copy::-webkit-scrollbar {
  display: none;
}

.npc-poster-shadow {
  text-shadow:
    0 1px 2px rgba(2, 6, 23, 0.95),
    0 0 8px rgba(2, 6, 23, 0.8),
    0 2px 18px rgba(2, 6, 23, 0.7);
}
</style>
