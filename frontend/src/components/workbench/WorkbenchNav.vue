<script setup lang="ts">
import type { Component } from 'vue'

export interface WorkbenchNavItem {
  id: string
  label: string
  icon?: Component
  /** Count or short status; hidden when null/undefined/0. */
  badge?: string | number | null
  badgeTone?: 'neutral' | 'warn' | 'danger' | 'accent'
}

export interface WorkbenchNavGroup {
  title: string
  items: WorkbenchNavItem[]
}

/** Grouped sidebar navigation. One accent color for the active entry, nothing else. */
defineProps<{ groups: WorkbenchNavGroup[]; active: string }>()
const emit = defineEmits<{ select: [id: string] }>()

const BADGE_TONE = {
  neutral: 'text-wb-muted bg-wb-raised',
  accent: 'text-wb-accent-text bg-wb-accent-soft',
  warn: 'text-wb-warn-text bg-wb-warn-soft',
  danger: 'text-wb-danger-text bg-wb-danger-soft',
}
</script>

<template>
  <nav class="space-y-5" aria-label="Sections">
    <div v-for="group in groups" :key="group.title" class="space-y-0.5">
      <p class="wb-overline px-3 pb-1">{{ group.title }}</p>
      <button
        v-for="item in group.items"
        :key="item.id"
        type="button"
        :aria-current="active === item.id ? 'page' : undefined"
        :class="[
          'w-full flex items-center gap-2.5 rounded-md px-3 py-2 text-left transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
          active === item.id
            ? 'bg-wb-accent-soft text-wb-accent-text'
            : 'text-wb-body hover:bg-wb-raised hover:text-wb-strong',
        ]"
        @click="emit('select', item.id)"
      >
        <component :is="item.icon" v-if="item.icon" class="w-4 h-4 shrink-0" aria-hidden="true" />
        <span class="wb-label !text-current flex-1 truncate">{{ item.label }}</span>
        <span
          v-if="item.badge"
          :class="['wb-hint !text-current rounded-md px-1.5 tabular-nums', BADGE_TONE[item.badgeTone ?? 'neutral']]"
        >
          {{ item.badge }}
        </span>
      </button>
    </div>
  </nav>
</template>
