<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, ArrowRight, X } from 'lucide-vue-next'
import type { AdventureTemplateSummary } from '@/types'

const props = defineProps<{
  isOpen: boolean
  template: AdventureTemplateSummary | null
  isStarting?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm', templateId: string): void
}>()

const adventureTitle = computed(() => props.template?.title || 'This adventure')
const templateId = computed(() => props.template?.template_id || '')
const formatVersion = computed(() => props.template?.format_version || '')

function onConfirm(): void {
  if (!templateId.value || props.isStarting) return
  emit('confirm', templateId.value)
}
</script>

<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100 scale-100"
    leave-to-class="opacity-0 scale-95"
  >
    <div
      v-if="props.isOpen && props.template"
      class="fixed inset-0 z-[230] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 overflow-y-auto"
      @click.self="emit('close')"
    >
      <div
        class="w-full max-w-lg rounded-2xl bg-slate-900/95 border border-amber-500/30 shadow-[0_20px_60px_rgba(0,0,0,0.8)] overflow-hidden font-ui"
        role="dialog"
        aria-modal="true"
        aria-labelledby="engine-outdated-title"
      >
        <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-4 bg-gradient-to-r from-amber-500/15 via-transparent to-transparent">
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 shrink-0 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
              <AlertTriangle class="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h3 id="engine-outdated-title" class="text-lg font-black text-white font-display uppercase tracking-wider">
                Engine out of date
              </h3>
              <p class="text-xs text-slate-400 mt-0.5">
                <span class="font-bold text-amber-400">{{ adventureTitle }}</span>
                was built for a newer engine version.
              </p>
            </div>
          </div>
          <button
            class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Close"
            aria-label="Close"
            @click="emit('close')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="px-6 py-5 space-y-3">
          <p class="text-sm text-slate-200 leading-relaxed">
            This adventure uses adventure format
            <span v-if="formatVersion" class="font-mono text-amber-300">v{{ formatVersion }}</span>
            <span v-else>of a newer generation</span>, which this engine build does not fully understand.
            You can still start it, but parts of the adventure may not behave as intended.
          </p>
          <p class="text-sm text-slate-400 leading-relaxed">
            Unexpected effects are possible: unknown rules, items or script hooks may be ignored or
            misinterpreted. Updating TaleWeaver to the latest version is the safe option.
          </p>
        </div>

        <div class="px-6 py-4 border-t border-white/10 flex flex-col sm:flex-row sm:justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="props.isStarting"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-200 text-sm font-black uppercase tracking-widest hover:bg-amber-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            :disabled="props.isStarting"
            @click="onConfirm"
          >
            <span v-if="props.isStarting" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            <span>{{ props.isStarting ? 'Starting...' : 'Start anyway' }}</span>
            <ArrowRight v-if="!props.isStarting" class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
