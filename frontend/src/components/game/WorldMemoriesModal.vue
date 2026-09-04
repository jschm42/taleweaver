<script setup lang="ts">
import { ref, computed } from 'vue'
import { X, BrainCircuit, Globe, MapPin, User, Sparkles, BookOpen, Clock } from 'lucide-vue-next'
import type { WorldMemory } from '@/types'

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
      class: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
      icon: 'ra ra-sun',
    }
  }
  if (norm === 'negative') {
    return {
      label: 'Negative',
      class: 'bg-rose-500/15 border-rose-500/30 text-rose-400',
      icon: 'ra ra-lightning-storm',
    }
  }
  return {
    label: 'Neutral',
    class: 'bg-sky-500/15 border-sky-500/30 text-sky-400',
    icon: 'ra ra-gem',
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in" @click.self="emit('close')">
    <div class="w-full max-w-2xl max-h-[85vh] rounded-3xl bg-slate-900 border border-white/10 shadow-2xl flex flex-col overflow-hidden" @click.stop>
      <!-- Header -->
      <div class="px-6 py-5 border-b border-white/10 flex items-center justify-between bg-slate-950/60 shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0 shadow-inner">
            <BrainCircuit class="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h3 class="text-base sm:text-lg font-black text-white font-display uppercase tracking-wider flex items-center gap-2">
              World Memories & Chronicle
            </h3>
            <p class="text-xs text-slate-400">
              Persistent consequences, NPC memories, and long-term history.
            </p>
          </div>
        </div>
        <button
          type="button"
          class="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-white/5 transition-colors cursor-pointer"
          @click="emit('close')"
          title="Close"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Navigation Tabs (if chronicle summary exists) -->
      <div v-if="chronicleText" class="flex border-b border-white/10 bg-slate-950/30 px-6 pt-3 gap-2 shrink-0">
        <button
          type="button"
          @click="activeTab = 'memories'"
          class="px-4 py-2.5 text-xs font-black uppercase tracking-wider rounded-t-xl border-b-2 transition-all flex items-center gap-2 cursor-pointer"
          :class="[
            activeTab === 'memories'
              ? 'border-amber-400 text-amber-300 bg-white/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          ]"
        >
          <Sparkles class="w-3.5 h-3.5" />
          <span>Active Memories ({{ memoryList.length }})</span>
        </button>
        <button
          type="button"
          @click="activeTab = 'chronicle'"
          class="px-4 py-2.5 text-xs font-black uppercase tracking-wider rounded-t-xl border-b-2 transition-all flex items-center gap-2 cursor-pointer"
          :class="[
            activeTab === 'chronicle'
              ? 'border-amber-400 text-amber-300 bg-white/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          ]"
        >
          <BookOpen class="w-3.5 h-3.5" />
          <span>Compressed Chronicle</span>
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto p-6 space-y-4 min-h-0">
        <!-- TAB 1: World Memories List -->
        <div v-if="activeTab === 'memories'" class="space-y-3">
          <div v-if="memoryList.length === 0" class="flex flex-col items-center justify-center py-12 text-center text-slate-500 space-y-3">
            <div class="w-12 h-12 rounded-full bg-slate-800/80 border border-slate-700/50 flex items-center justify-center">
              <BrainCircuit class="w-6 h-6 text-slate-600" />
            </div>
            <div>
              <h4 class="text-sm font-bold text-slate-400 uppercase tracking-wider">No World Memories Yet</h4>
              <p class="text-xs text-slate-500 max-w-sm mt-1">
                When your decisions have enduring consequences on characters, factions, or places, the GM will record them here.
              </p>
            </div>
          </div>

          <div
            v-for="(mem, idx) in memoryList"
            :key="idx"
            class="p-4 rounded-2xl bg-white/[0.03] border border-white/10 hover:border-white/20 transition-all space-y-2.5 shadow-sm"
          >
            <!-- Badge Row -->
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <!-- Scope Badge -->
                <span
                  class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider border flex items-center gap-1.5"
                  :class="[
                    mem.scope === 'global'
                      ? 'bg-purple-500/15 border-purple-500/30 text-purple-300'
                      : 'bg-amber-500/15 border-amber-500/30 text-amber-300'
                  ]"
                >
                  <Globe v-if="mem.scope === 'global'" class="w-3 h-3" />
                  <MapPin v-else class="w-3 h-3" />
                  <span>{{ mem.scope === 'global' ? 'Global Realm' : (mem.scene_id ? `Local (${mem.scene_id})` : 'Local Scene') }}</span>
                </span>

                <!-- Emotion Badge -->
                <span
                  class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider border flex items-center gap-1.5"
                  :class="getEmotionBadge(mem.emotion).class"
                >
                  <i :class="getEmotionBadge(mem.emotion).icon" class="text-xs"></i>
                  <span>{{ getEmotionBadge(mem.emotion).label }}</span>
                </span>
              </div>

              <!-- NPC Badge if present -->
              <span
                v-if="mem.npc_id"
                class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-800/80 border border-slate-700/60 text-slate-300 flex items-center gap-1"
              >
                <User class="w-3 h-3 text-slate-400" />
                <span>NPC: {{ mem.npc_id }}</span>
              </span>
            </div>

            <!-- Description -->
            <p class="text-sm text-slate-200 leading-relaxed font-serif tracking-wide">
              {{ mem.description }}
            </p>
          </div>
        </div>

        <!-- TAB 2: Compressed Chronicle Summary -->
        <div v-else-if="activeTab === 'chronicle'" class="space-y-4">
          <div class="p-4 rounded-2xl bg-amber-500/5 border border-amber-500/20 text-xs text-amber-200/90 leading-relaxed">
            <div class="flex items-center gap-2 font-bold uppercase tracking-wider mb-1 text-amber-300">
              <BookOpen class="w-4 h-4" />
              <span>Prior Adventure Narrative</span>
            </div>
            This chronicle summary preserves past story turns that have rotated out of the active memory window. It is automatically injected into every GM narration prompt.
          </div>

          <div class="p-5 rounded-2xl bg-black/40 border border-white/10 text-slate-300 text-sm leading-relaxed font-serif whitespace-pre-line shadow-inner">
            {{ chronicleText }}
          </div>

          <div v-if="chronicleUpdatedAt" class="flex items-center gap-1.5 text-[11px] text-slate-500 px-1 font-mono">
            <Clock class="w-3.5 h-3.5 text-slate-600" />
            <span>Last summarized: {{ chronicleUpdatedAt }}</span>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-white/10 flex justify-end bg-slate-950/60 shrink-0">
        <button
          type="button"
          class="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold uppercase tracking-wider transition-colors cursor-pointer"
          @click="emit('close')"
        >
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.font-display {
  font-family: 'Acme', sans-serif;
  letter-spacing: 0.05em;
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
