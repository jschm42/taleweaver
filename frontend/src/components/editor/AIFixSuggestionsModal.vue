<script setup lang="ts">
import { computed } from 'vue'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Wand2,
  X,
} from 'lucide-vue-next'
import type { FixProposal } from '@/services/adventureService'

const props = defineProps<{
  open: boolean
  proposals: FixProposal[]
  loading: boolean
  applying: boolean
  selectedIndex: number
  findingCode: string
  findingMessage: string
  findingLocation?: string | null
  hasBackupConfirmed: boolean
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', index: number): void
  (e: 'apply'): void
  (e: 'toggle-backup', value: boolean): void
  (e: 'retry'): void
}>()

const selectedProposal = computed<FixProposal | null>(() => {
  if (props.selectedIndex < 0) return null
  return props.proposals[props.selectedIndex] ?? null
})

const canApply = computed(() => {
  return (
    !props.applying &&
    !props.loading &&
    selectedProposal.value !== null &&
    props.hasBackupConfirmed
  )
})

function describeTarget(targetType: string, targetId?: string | null): string {
  const id = (targetId ?? '').trim()
  if (!id) return targetType
  return `${targetType} \u201c${id}\u201d`
}
</script>

<template>
  <div
    v-if="props.open"
    class="fixed inset-0 z-[260] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4"
    role="dialog"
    aria-modal="true"
    @click.self="emit('close')"
  >
    <div class="w-full max-w-3xl rounded-2xl border border-violet-500/30 bg-slate-900 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-4 shrink-0">
        <div class="flex items-start gap-3 min-w-0">
          <div class="w-10 h-10 rounded-full border border-violet-400/40 bg-violet-500/15 flex items-center justify-center shrink-0 mt-0.5">
            <Wand2 class="w-5 h-5 text-violet-300" />
          </div>
          <div class="min-w-0">
            <h3 class="text-lg font-black text-white flex items-center gap-2">
              AI Fix Suggestions
              <span class="px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-widest bg-violet-500/15 border border-violet-500/30 text-violet-200">
                {{ props.proposals.length }} / 3 options
              </span>
            </h3>
            <p class="text-xs text-slate-400 mt-1">
              The AI generated up to three different ways to resolve this finding. Pick one to apply.
            </p>
          </div>
        </div>
        <button
          class="text-slate-400 hover:text-white transition-colors shrink-0"
          :disabled="props.applying"
          @click="emit('close')"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="px-6 py-4 border-b border-white/10 shrink-0">
        <div class="rounded-xl border border-white/10 bg-white/5 px-4 py-3 space-y-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="px-2 py-0.5 rounded-md bg-amber-500/15 border border-amber-500/30 text-amber-200 text-[10px] font-black uppercase tracking-widest">
              Finding
            </span>
            <code class="text-[11px] font-mono text-slate-300">{{ props.findingCode }}</code>
            <span v-if="props.findingLocation" class="text-[10px] text-slate-500 font-mono">
              {{ props.findingLocation }}
            </span>
          </div>
          <p class="text-xs text-slate-300 leading-relaxed">{{ props.findingMessage }}</p>
        </div>
      </div>

      <div class="px-6 py-5 overflow-y-auto grow space-y-4">
        <div
          v-if="props.loading"
          class="flex flex-col items-center justify-center gap-3 py-12 text-slate-400"
        >
          <Loader2 class="w-8 h-8 animate-spin text-violet-300" />
          <p class="text-xs uppercase tracking-widest font-black">AI is drafting fixes&hellip;</p>
          <p class="text-[11px] text-slate-500">Up to three suggestions will be proposed.</p>
        </div>

        <div
          v-else-if="!props.loading && props.errorMessage"
          class="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 flex items-start gap-3"
        >
          <AlertTriangle class="w-5 h-5 text-rose-300 shrink-0 mt-0.5" />
          <div class="flex-1 space-y-2 text-sm text-rose-100 leading-relaxed">
            <p class="font-bold">{{ props.errorMessage }}</p>
            <p class="text-[11px] text-rose-200/80">
              The fix could not be applied. Try generating fresh suggestions, then pick a different option.
            </p>
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg border border-rose-400/50 text-rose-100 text-xs font-black uppercase tracking-widest hover:bg-rose-500/20 transition-colors flex items-center gap-2 disabled:opacity-50"
              :disabled="props.applying"
              @click="emit('retry')"
            >
              <RefreshCw class="w-3 h-3" />
              <span>Retry</span>
            </button>
          </div>
        </div>

        <div
          v-else-if="props.proposals.length === 0"
          class="rounded-xl border border-white/10 bg-white/5 px-4 py-6 text-center text-sm text-slate-300"
        >
          <ShieldAlert class="w-6 h-6 mx-auto text-slate-400 mb-2" />
          The AI declined to suggest a fix for this finding. Try fixing it manually or rerun the AI validation.
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="(proposal, idx) in props.proposals"
            :key="`${proposal.title}-${idx}`"
            class="rounded-2xl border transition-all p-4 space-y-3"
            :class="
              props.selectedIndex === idx
                ? 'border-violet-400/60 bg-violet-500/10 shadow-lg shadow-violet-900/30'
                : 'border-white/10 bg-white/5 hover:border-white/20'
            "
          >
            <label class="flex items-start gap-3 cursor-pointer">
              <input
                type="radio"
                name="ai-fix-option"
                class="mt-1 accent-violet-500 cursor-pointer"
                :checked="props.selectedIndex === idx"
                @change="emit('select', idx)"
              />
              <div class="flex-1 min-w-0 space-y-2">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-widest bg-violet-500/15 border border-violet-500/30 text-violet-200">
                    Option {{ idx + 1 }}
                  </span>
                  <h4 class="text-sm font-black text-white">{{ proposal.title }}</h4>
                </div>
                <p class="text-xs text-slate-300 leading-relaxed">{{ proposal.summary }}</p>
                <p
                  v-if="proposal.rationale"
                  class="text-[11px] text-slate-400 italic leading-relaxed"
                >
                  Rationale: {{ proposal.rationale }}
                </p>
                <div class="rounded-lg border border-white/10 bg-slate-950/60 p-3 space-y-2">
                  <p class="text-[10px] uppercase tracking-widest text-slate-500 font-black">
                    What will change
                  </p>
                  <ul class="space-y-1.5">
                    <li
                      v-for="(patch, pIdx) in proposal.patches"
                      :key="`${patch.target_type}-${patch.target_id || ''}-${pIdx}`"
                      class="flex items-start gap-2 text-[11px] text-slate-300"
                    >
                      <ArrowRight class="w-3 h-3 text-violet-300 mt-0.5 shrink-0" />
                      <span class="leading-relaxed">
                        <span class="font-bold text-violet-200">{{ describeTarget(patch.target_type, patch.target_id) }}</span>
                        <span v-if="patch.description"> &mdash; {{ patch.description }}</span>
                      </span>
                    </li>
                  </ul>
                </div>
              </div>
            </label>
          </div>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-white/10 space-y-3 shrink-0 bg-slate-950/50">
        <label class="flex items-start gap-3 text-xs text-slate-200 leading-relaxed cursor-pointer select-none">
          <input
            type="checkbox"
            class="mt-0.5 accent-rose-500 cursor-pointer"
            :checked="props.hasBackupConfirmed"
            @change="emit('toggle-backup', ($event.target as HTMLInputElement).checked)"
          />
          <span>
            <span class="font-black text-rose-200">Important &mdash;</span>
            I have made a copy of this adventure (or accept the risk that AI edits will overwrite
            my current data). The engine does not auto-rollback these changes.
          </span>
        </label>

        <div class="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-start gap-2 text-[11px] text-amber-100">
          <AlertTriangle class="w-4 h-4 text-amber-300 shrink-0 mt-0.5" />
          <p class="leading-relaxed">
            AI-generated fixes can be subtly wrong. We strongly recommend exporting the
            adventure (<code class="font-mono">.adv</code>) before applying any of these patches.
          </p>
        </div>

        <div class="flex items-center justify-end gap-3">
          <button
            type="button"
            class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors disabled:opacity-50"
            :disabled="props.applying"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-5 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-black uppercase tracking-wider transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed flex items-center gap-2"
            :disabled="!canApply"
            @click="emit('apply')"
          >
            <Loader2 v-if="props.applying" class="w-4 h-4 animate-spin" />
            <CheckCircle2 v-else class="w-4 h-4" />
            <span>{{ props.applying ? 'Applying\u2026' : 'Apply selected fix' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
