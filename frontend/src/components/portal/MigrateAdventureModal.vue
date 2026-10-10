<script setup lang="ts">
import { computed } from 'vue'
import { X, Sparkles, Wrench, AlertTriangle, ArrowRight, ShieldAlert } from 'lucide-vue-next'
import type { AdventureTemplateSummary } from '@/types'

const props = defineProps<{
  isOpen: boolean
  template: AdventureTemplateSummary | null
  isMigrating?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'migrate-format', templateId: string): void
  (e: 'cover', templateId: string): void
}>()

const adventureTitle = computed(() => props.template?.title || 'Unknown Adventure')
const templateId = computed(() => props.template?.template_id || '')

function onMigrateFormat() {
  if (!templateId.value || props.isMigrating) return
  emit('migrate-format', templateId.value)
}

function onCover() {
  if (!templateId.value || props.isMigrating) return
  emit('cover', templateId.value)
  emit('close')
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
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 overflow-y-auto"
      @click.self="emit('close')"
    >
      <div
        class="w-full max-w-xl rounded-2xl bg-slate-900/95 border border-white/15 shadow-[0_20px_60px_rgba(0,0,0,0.8)] overflow-hidden font-ui relative"
      >
        <!-- Modal Header -->
        <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-4 bg-gradient-to-r from-amber-500/10 via-transparent to-transparent">
          <div class="flex items-center gap-3.5">
            <div class="w-11 h-11 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-400 flex items-center justify-center shrink-0 shadow-lg shadow-amber-500/10">
              <Wrench class="w-5 h-5" />
            </div>
            <div>
              <h3 class="text-lg font-black text-white font-display uppercase tracking-wider">
                Migrate Adventure
              </h3>
              <p class="text-xs text-slate-400 mt-0.5">
                Target: <span class="font-bold text-amber-400">{{ adventureTitle }}</span>
              </p>
            </div>
          </div>

          <button
            @click="emit('close')"
            :disabled="props.isMigrating"
            class="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-40"
            title="Close dialog"
          >
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-6 space-y-5">
          <!-- Information notice -->
          <div class="p-3.5 rounded-xl bg-slate-800/80 border border-white/10 flex items-start gap-3 text-xs leading-relaxed text-slate-300">
            <ShieldAlert class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <p>
              This adventure was created in an older format without sequence support. To play or edit it, it needs to be updated to the current format. Choose one of the following two options:
            </p>
          </div>

          <!-- Two Options Grid / Cards -->
          <div class="space-y-4">
            <!-- Option 1: Data Format Migration -->
            <div class="rounded-xl border border-white/10 hover:border-amber-500/50 bg-white/[0.02] hover:bg-amber-500/[0.04] p-4 transition-all duration-200 group">
              <div class="flex items-start justify-between gap-3 mb-2.5">
                <div class="flex items-center gap-2.5">
                  <div class="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-300 flex items-center justify-center">
                    <Wrench class="w-4 h-4" />
                  </div>
                  <div>
                    <h4 class="text-sm font-bold text-white group-hover:text-amber-300 transition-colors">
                      Option 1: Migrate Data Format
                    </h4>
                    <span class="text-[10px] font-semibold text-amber-400/90 uppercase tracking-wider">
                      Instant In-Place Upgrade
                    </span>
                  </div>
                </div>
              </div>

              <p class="text-xs text-slate-400 leading-relaxed mb-3">
                Upgrades the adventure data format to the latest version. The existing walkthrough text is converted into <strong class="text-slate-200">Sequence 1 ("Main Journey")</strong>.
              </p>

              <!-- Prominent User Notice -->
              <div class="p-3 rounded-lg bg-amber-500/10 border border-amber-500/25 flex items-start gap-2.5 text-[11px] text-amber-300 mb-3">
                <AlertTriangle class="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                <span>
                  <strong>Note:</strong> No additional sequences will be created automatically. The adventure will run with this single sequence. You can inspect and expand sequences at any time in the Adventure Editor.
                </span>
              </div>

              <button
                @click="onMigrateFormat"
                :disabled="props.isMigrating"
                class="w-full py-2.5 px-4 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 hover:text-white text-xs font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
              >
                <i v-if="props.isMigrating" class="ra ra-cycle animate-spin text-sm"></i>
                <Wrench v-else class="w-4 h-4" />
                <span>{{ props.isMigrating ? 'Migrating Format...' : 'Migrate Format Now' }}</span>
              </button>
            </div>

            <!-- Option 2: Cover Adventure -->
            <div class="rounded-xl border border-white/10 hover:border-purple-500/50 bg-white/[0.02] hover:bg-purple-500/[0.04] p-4 transition-all duration-200 group">
              <div class="flex items-start justify-between gap-3 mb-2.5">
                <div class="flex items-center gap-2.5">
                  <div class="w-8 h-8 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-300 flex items-center justify-center">
                    <Sparkles class="w-4 h-4" />
                  </div>
                  <div>
                    <h4 class="text-sm font-bold text-white group-hover:text-purple-300 transition-colors">
                      Option 2: Create Adventure Cover
                    </h4>
                    <span class="text-[10px] font-semibold text-purple-400/90 uppercase tracking-wider">
                      AI World-Builder Reinterpretation
                    </span>
                  </div>
                </div>
              </div>

              <p class="text-xs text-slate-400 leading-relaxed mb-3">
                Uses the AI World-Builder to generate a fresh cover version of this adventure. It restructures the story into rich, multi-stage sequences, modern scenes, and quests in the new format.
              </p>

              <button
                @click="onCover"
                :disabled="props.isMigrating"
                class="w-full py-2.5 px-4 rounded-xl bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-purple-300 hover:text-white text-xs font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
              >
                <Sparkles class="w-4 h-4" />
                <span>Open Cover Generator</span>
                <ArrowRight class="w-4 h-4 ml-1" />
              </button>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-white/10 flex justify-end bg-black/20">
          <button
            @click="emit('close')"
            :disabled="props.isMigrating"
            class="px-4 py-2 rounded-xl text-xs font-bold text-slate-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
