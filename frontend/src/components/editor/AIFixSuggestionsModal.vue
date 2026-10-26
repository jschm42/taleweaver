<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, Loader2, RefreshCw, ShieldAlert, Wand2, X } from 'lucide-vue-next'
import type { FixProposal } from '@/services/adventureService'
import FixProposalList from '@/components/editor/FixProposalList.vue'
import ProposalApplyFooter from '@/components/editor/ProposalApplyFooter.vue'

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

        <FixProposalList
          v-else
          :proposals="props.proposals"
          :selected-index="props.selectedIndex"
          radio-name="ai-fix-option"
          @select="emit('select', $event)"
        />
      </div>

      <ProposalApplyFooter
        :has-backup-confirmed="props.hasBackupConfirmed"
        :applying="props.applying"
        :can-apply="canApply"
        apply-label="Apply selected fix"
        @toggle-backup="emit('toggle-backup', $event)"
        @cancel="emit('close')"
        @apply="emit('apply')"
      />
    </div>
  </div>
</template>
