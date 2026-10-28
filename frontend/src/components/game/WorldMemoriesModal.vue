<script setup lang="ts">
import { ref, computed } from 'vue'
import { X, BrainCircuit, Globe, MapPin, User, Sparkles, BookOpen, Clock } from 'lucide-vue-next'
import type { WorldMemory } from '@/types'
import { useDialogSkin } from '@/skins/dialogSkin'
import { vDropCap } from '@/skins/vDropCap'
import { formatEntityRefs } from '@/utils/entityRefs'

const props = defineProps<{
  memories?: WorldMemory[]
  compressedHistory?: {
    summary?: string
    updated_at?: string
    [key: string]: any
  } | string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { activeSkin, skinStyle } = useDialogSkin()

const activeTab = ref<'memories' | 'chronicle'>('memories')

const memoryList = computed<WorldMemory[]>(() => {
  return Array.isArray(props.memories) ? props.memories : []
})

const chronicleText = computed<string>(() => {
  if (!props.compressedHistory) return ''
  if (typeof props.compressedHistory === 'string') return props.compressedHistory
  return props.compressedHistory.summary || ''
})

const chronicleUpdatedAt = computed<string | null>(() => {
  if (props.compressedHistory && typeof props.compressedHistory === 'object' && props.compressedHistory.updated_at) {
    try {
      return new Date(props.compressedHistory.updated_at).toLocaleString()
    } catch {
      return props.compressedHistory.updated_at
    }
  }
  return null
})

function getEmotionBadge(emotion?: string) {
  const norm = (emotion || 'neutral').toLowerCase()
  if (norm === 'positive') {
    return {
      label: 'Positive',
      class: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-500',
      icon: 'ra ra-sun',
    }
  }
  if (norm === 'negative') {
    return {
      label: 'Negative',
      class: 'bg-rose-500/15 border-rose-500/30 text-rose-500',
      icon: 'ra ra-lightning-storm',
    }
  }
  return {
    label: 'Neutral',
    class: 'bg-sky-500/15 border-sky-500/30 text-sky-500',
    icon: 'ra ra-gem',
  }
}
</script>

<template>
  <div
    class="tw-skin tw-dialog-backdrop fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
    :data-skin="activeSkin"
    :style="skinStyle"
    @click.self="emit('close')"
  >
    <div class="tw-dialog w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden" role="dialog" aria-modal="true" aria-label="World Memories" @click.stop>
      <!-- Header -->
      <div class="tw-dialog-header px-6 py-5 flex items-center justify-between shrink-0">
        <div class="flex items-center gap-3">
          <BrainCircuit class="w-6 h-6 shrink-0 tw-dialog-eyebrow" />
          <div>
            <h3 class="tw-dialog-title text-lg sm:text-xl">World Memories & Chronicle</h3>
            <p class="tw-muted text-xs mt-0.5">
              Persistent consequences, NPC memories, and long-term history.
            </p>
          </div>
        </div>
        <button type="button" class="tw-dialog-icon-button p-2" title="Close" aria-label="Close" @click="emit('close')">
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Navigation Tabs (if chronicle summary exists) -->
      <div v-if="chronicleText" class="tw-dialog-divider flex border-b px-6 py-3 gap-2 shrink-0" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'memories'"
          class="tw-tab"
          :class="{ 'tw-tab--active': activeTab === 'memories' }"
          @click="activeTab = 'memories'"
        >
          <Sparkles class="w-3.5 h-3.5" />
          <span>Active Memories</span>
          <span class="tw-tab-count">{{ memoryList.length }}</span>
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'chronicle'"
          class="tw-tab"
          :class="{ 'tw-tab--active': activeTab === 'chronicle' }"
          @click="activeTab = 'chronicle'"
        >
          <BookOpen class="w-3.5 h-3.5" />
          <span>Compressed Chronicle</span>
        </button>
      </div>

      <!-- Body -->
      <div class="tw-dialog-scroll flex-1 overflow-y-auto p-6 space-y-4 min-h-0">
        <!-- TAB 1: World Memories List -->
        <div v-if="activeTab === 'memories'" class="space-y-3">
          <div v-if="memoryList.length === 0" class="tw-dialog-slot flex flex-col items-center justify-center py-12 px-6 text-center space-y-3">
            <BrainCircuit class="w-8 h-8 opacity-60" />
            <div>
              <h4 class="tw-panel-title">No World Memories Yet</h4>
              <p class="text-xs max-w-sm mt-1">
                When your decisions have enduring consequences on characters, factions, or places, the GM will record them here.
              </p>
            </div>
          </div>

          <div
            v-for="(mem, idx) in memoryList"
            :key="idx"
            class="tw-card p-4 space-y-2.5"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span
                  class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider border flex items-center gap-1.5"
                  :class="mem.scope === 'global'
                    ? 'bg-purple-500/15 border-purple-500/30 text-purple-500'
                    : 'bg-amber-500/15 border-amber-500/30 text-amber-600'"
                >
                  <Globe v-if="mem.scope === 'global'" class="w-3 h-3" />
                  <MapPin v-else class="w-3 h-3" />
                  <span>{{ mem.scope === 'global' ? 'Global Realm' : (mem.scene_id ? `Local (${mem.scene_id})` : 'Local Scene') }}</span>
                </span>

                <span
                  class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider border flex items-center gap-1.5"
                  :class="getEmotionBadge(mem.emotion).class"
                >
                  <i :class="getEmotionBadge(mem.emotion).icon" class="text-xs"></i>
                  <span>{{ getEmotionBadge(mem.emotion).label }}</span>
                </span>
              </div>

              <span v-if="mem.npc_id" class="tw-dialog-chip flex items-center gap-1">
                <User class="w-3 h-3" />
                <span>NPC: {{ mem.npc_id }}</span>
              </span>
            </div>

            <p class="text-sm leading-relaxed font-serif tracking-wide" v-html="formatEntityRefs(mem.description)"></p>
          </div>
        </div>

        <!-- TAB 2: Compressed Chronicle Summary -->
        <div v-else-if="activeTab === 'chronicle'" class="space-y-4">
          <div class="tw-dialog-slot !border-solid p-4 text-xs leading-relaxed">
            <div class="tw-dialog-eyebrow flex items-center gap-2 mb-1">
              <BookOpen class="w-4 h-4" />
              <span>Prior Adventure Narrative</span>
            </div>
            This chronicle summary preserves past story turns that have rotated out of the active memory window. It is automatically injected into every GM narration prompt.
          </div>

          <section class="tw-narration">
            <p v-drop-cap class="tw-narration-text whitespace-pre-line">{{ chronicleText }}</p>
          </section>

          <div v-if="chronicleUpdatedAt" class="tw-muted flex items-center gap-1.5 text-[11px] px-1 font-mono">
            <Clock class="w-3.5 h-3.5" />
            <span>Last summarized: {{ chronicleUpdatedAt }}</span>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="tw-dialog-divider px-6 py-4 border-t flex justify-end shrink-0">
        <button type="button" class="tw-dialog-button tw-dialog-button--ghost" @click="emit('close')">
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
