<script setup lang="ts">
import { ref, watch } from 'vue'
import { ArrowLeft, Menu, X } from 'lucide-vue-next'
import UiIconButton from '@/components/ui/UiIconButton.vue'

/**
 * Frame of every Workbench page: sidebar (title, navigation, footer) and a scrolling
 * content column. Below `lg` the sidebar becomes a menu that opens over the content.
 */
const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    backLabel?: string
    /** Changes whenever the page changes; closes the mobile menu and scrolls to top. */
    pageKey?: string
    wide?: boolean
  }>(),
  { subtitle: '', backLabel: 'Back', pageKey: '', wide: false },
)

const emit = defineEmits<{ back: [] }>()

const menuOpen = ref(false)
const contentEl = ref<HTMLElement | null>(null)

watch(
  () => props.pageKey,
  () => {
    menuOpen.value = false
    contentEl.value?.scrollTo({ top: 0 })
  },
)
</script>

<template>
  <div class="wb-root h-full flex bg-wb-canvas">
    <aside
      :class="[
        'w-60 shrink-0 flex-col border-r border-wb-line bg-wb-surface',
        menuOpen ? 'fixed inset-y-0 left-0 z-40 flex shadow-wb-float' : 'hidden lg:flex',
      ]"
    >
      <div class="flex items-center gap-2 px-3 py-4 border-b border-wb-line">
        <UiIconButton :icon="ArrowLeft" :label="backLabel" size="sm" @click="emit('back')" />
        <div class="min-w-0 flex-1">
          <p class="wb-subheading truncate">{{ title }}</p>
          <p v-if="subtitle" class="wb-hint truncate">{{ subtitle }}</p>
        </div>
        <UiIconButton v-if="menuOpen" :icon="X" label="Close menu" size="sm" class="lg:hidden" @click="menuOpen = false" />
      </div>
      <div class="flex-1 overflow-y-auto px-2 py-4">
        <slot name="nav" />
      </div>
      <div v-if="$slots.footer" class="border-t border-wb-line px-3 py-3">
        <slot name="footer" />
      </div>
    </aside>
    <div v-if="menuOpen" class="fixed inset-0 z-30 bg-black/50 lg:hidden" aria-hidden="true" @click="menuOpen = false" />

    <div ref="contentEl" class="flex-1 min-w-0 overflow-y-auto">
      <div class="lg:hidden sticky top-0 z-20 flex items-center gap-2 border-b border-wb-line bg-wb-surface px-3 py-2">
        <UiIconButton :icon="Menu" label="Open menu" size="sm" @click="menuOpen = true" />
        <p class="wb-subheading truncate">{{ title }}</p>
      </div>
      <main :class="['mx-auto px-4 py-6 sm:px-6 xl:px-8 xl:py-8 space-y-6', wide ? 'max-w-7xl' : 'max-w-5xl']">
        <slot />
      </main>
    </div>
  </div>
</template>
