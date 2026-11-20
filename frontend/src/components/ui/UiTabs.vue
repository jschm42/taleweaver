<script setup lang="ts" generic="T extends string">
/** Underlined tab row. Arrow keys move between tabs; panels are rendered by the caller. */
const model = defineModel<T>({ required: true })

const props = defineProps<{ tabs: { id: T; label: string; count?: number | null }[]; label: string }>()

function move(step: number): void {
  const index = props.tabs.findIndex((tab) => tab.id === model.value)
  const next = props.tabs[(index + step + props.tabs.length) % props.tabs.length]
  if (next) model.value = next.id
}
</script>

<template>
  <div
    role="tablist"
    :aria-label="label"
    class="flex gap-5 overflow-x-auto border-b border-wb-line"
    @keydown.right.prevent="move(1)"
    @keydown.left.prevent="move(-1)"
  >
    <button
      v-for="tab in tabs"
      :key="tab.id"
      type="button"
      role="tab"
      :aria-selected="model === tab.id"
      :tabindex="model === tab.id ? 0 : -1"
      :class="[
        '-mb-px flex shrink-0 items-center gap-1.5 border-b-2 py-2.5 wb-label transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
        model === tab.id ? 'border-wb-accent !text-wb-accent-text' : 'border-transparent !text-wb-muted hover:!text-wb-strong',
      ]"
      @click="model = tab.id"
    >
      {{ tab.label }}
      <span v-if="tab.count" class="wb-hint tabular-nums">{{ tab.count }}</span>
    </button>
  </div>
</template>
