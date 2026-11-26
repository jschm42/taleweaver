<script setup lang="ts">
/** Searchable grid of 2:3 catalog tiles (image styles or tones); a click picks one and closes. */
import { computed, ref, watch, type Component } from 'vue'
import { Check, Search } from 'lucide-vue-next'
import type { CatalogTile } from '@/types'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'

const props = defineProps<{ title: string; items: CatalogTile[]; selectedId: string; icon: Component }>()
const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ select: [id: string] }>()

const query = ref('')

watch(open, (isOpen) => {
  if (isOpen) query.value = ''
})

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase()
  if (!needle) return props.items
  return props.items.filter((item) =>
    [item.name, item.description, item.instruction, item.id].some((text) => (text || '').toLowerCase().includes(needle)),
  )
})

function pick(id: string): void {
  emit('select', id)
  open.value = false
}
</script>

<template>
  <UiModal v-model:open="open" :title="`Choose ${title.toLowerCase()}`" :description="`${items.length} options`" size="xl">
    <div class="space-y-4">
      <UiInput v-model="query" type="search" :placeholder="`Search ${title.toLowerCase()}…`" data-autofocus />
      <UiEmptyState v-if="!filtered.length" :icon="Search" title="Nothing found" description="Try another word.">
        <template #action>
          <UiButton size="sm" @click="query = ''">Clear search</UiButton>
        </template>
      </UiEmptyState>
      <ul v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <li v-for="item in filtered" :key="item.id">
          <button
            type="button"
            :aria-pressed="item.id === selectedId"
            :class="[
              'group relative block aspect-[2/3] w-full overflow-hidden rounded-xl border bg-wb-raised text-left transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
              item.id === selectedId ? 'border-wb-accent ring-2 ring-wb-accent' : 'border-wb-line hover:border-wb-line-strong',
            ]"
            @click="pick(item.id)"
          >
            <img
              v-if="item.image_url"
              :src="item.image_url"
              :alt="item.name"
              loading="lazy"
              class="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
            <span v-else class="absolute inset-0 flex items-center justify-center pb-16 text-wb-faint">
              <component :is="icon" class="h-6 w-6" aria-hidden="true" />
            </span>
            <span class="pointer-events-none absolute inset-x-0 bottom-0 h-3/5 bg-gradient-to-t from-wb-canvas via-wb-canvas/80 to-transparent" />
            <span
              v-if="item.id === selectedId"
              class="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-md bg-wb-accent text-white"
            >
              <Check class="h-4 w-4" aria-hidden="true" />
              <span class="sr-only">Selected</span>
            </span>
            <span class="absolute inset-x-0 bottom-0 p-3">
              <span class="wb-label block truncate !text-wb-strong">{{ item.name }}</span>
              <span class="wb-hint line-clamp-2">{{ item.description }}</span>
            </span>
          </button>
        </li>
      </ul>
    </div>
  </UiModal>
</template>
