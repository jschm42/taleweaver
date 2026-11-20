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

/** Action menu behind a "…" button. Closes on selection, outside click and Esc. */
withDefaults(defineProps<{ items: MenuItem[]; label?: string; align?: 'left' | 'right' }>(), {
  label: 'More actions',
  align: 'right',
})

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const menuEl = ref<HTMLElement | null>(null)
const menuId = `menu-${useId()}`

const TONE = {
  default: 'text-wb-body hover:bg-wb-raised hover:text-wb-strong',
  danger: 'text-wb-danger-text hover:bg-wb-danger-soft',
  ai: 'text-wb-ai-text hover:bg-wb-ai-soft',
}

function entries(): HTMLButtonElement[] {
  return [...(menuEl.value?.querySelectorAll<HTMLButtonElement>('button:not([disabled])') ?? [])]
}

function handleDocumentClick(event: MouseEvent): void {
  if (rootEl.value && !rootEl.value.contains(event.target as Node)) close()
}

async function toggle(): Promise<void> {
  if (open.value) {
    close()
    return
  }
  open.value = true
  document.addEventListener('click', handleDocumentClick, true)
  await nextTick()
  entries()[0]?.focus()
}

function close(): void {
  open.value = false
  document.removeEventListener('click', handleDocumentClick, true)
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
    <div
      v-if="open"
      :id="menuId"
      ref="menuEl"
      role="menu"
      :aria-label="label"
      :class="[
        'absolute top-full z-50 mt-1 w-52 rounded-xl border border-wb-line-strong bg-wb-overlay py-1 shadow-wb-float font-wb',
        align === 'right' ? 'right-0' : 'left-0',
      ]"
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
  </div>
</template>
