<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, type Component } from 'vue'
import { MoreHorizontal } from 'lucide-vue-next'
import UiIconButton from '@/components/ui/UiIconButton.vue'

export interface MenuItem {
  label: string
  icon?: Component
  /** `danger` for destructive entries, `ai` for entries that call a model. */
  tone?: 'default' | 'danger' | 'ai'
  disabled?: boolean
  /** Draw a divider above this entry. */
  separated?: boolean
  onSelect: () => void
}

/**
 * Action menu behind a "…" button. Closes on selection, outside click, Esc, scroll and resize.
 * The list is teleported to <body> with a fixed position next to the button, so cards with
 * `overflow-hidden` or later siblings in a grid can neither clip nor cover it. It opens upward
 * when there is not enough room below.
 */
const props = withDefaults(defineProps<{ items: MenuItem[]; label?: string; align?: 'left' | 'right' }>(), {
  label: 'More actions',
  align: 'right',
})

const MENU_WIDTH = 208
const GAP = 4
const EDGE = 8

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const menuEl = ref<HTMLElement | null>(null)
const menuId = `menu-${useId()}`
const position = ref<Record<string, string>>({})

function placeMenu(): void {
  const trigger = rootEl.value?.getBoundingClientRect()
  if (!trigger) return
  const left = props.align === 'right' ? trigger.right - MENU_WIDTH : trigger.left
  const clampedLeft = Math.min(Math.max(EDGE, left), window.innerWidth - MENU_WIDTH - EDGE)
  const height = menuEl.value?.offsetHeight ?? 0
  const roomBelow = window.innerHeight - trigger.bottom
  const openUp = height > 0 && roomBelow < height + GAP + EDGE && trigger.top > roomBelow
  position.value = {
    left: `${clampedLeft}px`,
    top: openUp ? `${Math.max(EDGE, trigger.top - height - GAP)}px` : `${trigger.bottom + GAP}px`,
  }
}

const TONE = {
  default: 'text-wb-body hover:bg-wb-raised hover:text-wb-strong',
  danger: 'text-wb-danger-text hover:bg-wb-danger-soft',
  ai: 'text-wb-ai-text hover:bg-wb-ai-soft',
}

function entries(): HTMLButtonElement[] {
  return [...(menuEl.value?.querySelectorAll<HTMLButtonElement>('button:not([disabled])') ?? [])]
}

function handleDocumentClick(event: MouseEvent): void {
  const target = event.target as Node
  if (rootEl.value?.contains(target) || menuEl.value?.contains(target)) return
  close()
}

function handleViewportChange(event: Event): void {
  // Scrolling inside the menu itself must not close it.
  if (event.type === 'scroll' && menuEl.value?.contains(event.target as Node)) return
  close()
}

async function toggle(): Promise<void> {
  if (open.value) {
    close()
    return
  }
  placeMenu()
  open.value = true
  document.addEventListener('click', handleDocumentClick, true)
  window.addEventListener('scroll', handleViewportChange, true)
  window.addEventListener('resize', handleViewportChange)
  await nextTick()
  placeMenu()
  entries()[0]?.focus()
}

function close(): void {
  open.value = false
  document.removeEventListener('click', handleDocumentClick, true)
  window.removeEventListener('scroll', handleViewportChange, true)
  window.removeEventListener('resize', handleViewportChange)
}

function select(item: MenuItem): void {
  close()
  item.onSelect()
}

function moveFocus(step: number): void {
  const items = entries()
  const index = items.indexOf(document.activeElement as HTMLButtonElement)
  items[(index + step + items.length) % items.length]?.focus()
}

function handleEscape(): void {
  close()
  rootEl.value?.querySelector<HTMLButtonElement>('button')?.focus()
}

onBeforeUnmount(close)
</script>

<template>
  <div ref="rootEl" class="relative inline-flex" @keydown.esc.stop="handleEscape">
    <slot name="trigger" :toggle="toggle" :open="open">
      <UiIconButton
        :icon="MoreHorizontal"
        :label="label"
        size="sm"
        :aria-expanded="open"
        aria-haspopup="menu"
        :aria-controls="menuId"
        @click.stop="toggle"
      />
    </slot>
    <Teleport to="body">
    <div
      v-if="open"
      :id="menuId"
      ref="menuEl"
      role="menu"
      :aria-label="label"
      class="fixed z-[1000] w-52 rounded-xl border border-wb-line-strong bg-wb-overlay py-1 shadow-wb-float font-wb"
      :style="position"
      @keydown.esc.stop="handleEscape"
      @keydown.down.prevent="moveFocus(1)"
      @keydown.up.prevent="moveFocus(-1)"
    >
      <template v-for="item in items" :key="item.label">
        <div v-if="item.separated" class="my-1 h-px bg-wb-line" role="separator" />
        <button
          type="button"
          role="menuitem"
          :disabled="item.disabled"
          :class="[
            'flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:bg-wb-raised',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            TONE[item.tone ?? 'default'],
          ]"
          @click="select(item)"
        >
          <component :is="item.icon" v-if="item.icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
          <span class="wb-label !text-current truncate">{{ item.label }}</span>
        </button>
      </template>
    </div>
    </Teleport>
  </div>
</template>
