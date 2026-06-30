<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Bug,
  Download,
  Eraser,
  Loader2,
  ShieldCheck,
  Sparkles,
  Wand2,
} from 'lucide-vue-next'
import {
  adventureService,
  type AnnotatedValidationFinding,
  type AIFixSuggestionsRequest,
  type AIFixSuggestionsResponse,
  type FixProposal,
  type PersistedValidationRun,
  type ValidationAiSkippedReason,
  type ValidationFinding,
  type ValidationRunResponse,
  type ValidationSeverity,
} from '@/services/adventureService'
import AIFixSuggestionsModal from '@/components/editor/AIFixSuggestionsModal.vue'

type FilterKey = 'all' | 'errors' | 'warnings' | 'structural' | 'ai'

const props = defineProps<{
  templateId: string
  adventureTitle?: string
}>()

const emit = defineEmits<{
  (e: 'notify', message: string, type: 'error' | 'success' | 'info'): void
  (
    e: 'findings-count',
    total: number,
    errors: number,
    warnings: number,
    ai: number,
    structural: number,
  ): void
}>()

const findings = ref<AnnotatedValidationFinding[]>([])
const aiSkippedReason = ref<ValidationAiSkippedReason>(null)
const lastRunAt = ref<string | null>(null)
const isRunning = ref(false)
const isHydrating = ref(false)
const activeFilter = ref<FilterKey>('all')
const hasAutoRun = ref(false)

const errorCount = computed(
  () => findings.value.filter((f) => f.severity === 'error').length,
)
const warningCount = computed(
  () => findings.value.filter((f) => f.severity === 'warn').length,
)
const aiFindingCount = computed(
  () => findings.value.filter((f) => f.source === 'ai').length,
)
const structuralFindingCount = computed(
  () => findings.value.filter((f) => f.source === 'structural').length,
)

const filteredFindings = computed(() => {
  switch (activeFilter.value) {
    case 'errors':
      return findings.value.filter((f) => f.severity === 'error')
    case 'warnings':
      return findings.value.filter((f) => f.severity === 'warn')
    case 'structural':
      return findings.value.filter((f) => f.source === 'structural')
    case 'ai':
      return findings.value.filter((f) => f.source === 'ai')
    default:
      return findings.value
  }
})

async function runValidation(includeAi: boolean) {
  if (isRunning.value) return
  isRunning.value = true
  try {
    const resp: ValidationRunResponse = await adventureService.runValidation(
      props.templateId,
      includeAi,
    )
    mergeValidationResponse(resp)
    if (includeAi && aiSkippedReason.value === null && resp.ai_findings.length === 0) {
      emit('notify', 'AI validation finished with no findings.', 'success')
    }
  } catch (err: any) {
    emit(
      'notify',
      err?.message || 'Validation failed. See server logs for details.',
      'error',
    )
  } finally {
    isRunning.value = false
  }
}

function mergeValidationResponse(resp: ValidationRunResponse) {
  const extended: AnnotatedValidationFinding[] = [
    ...resp.structural_findings.map(
      (f): AnnotatedValidationFinding => ({ ...f, source: 'structural' }),
    ),
    ...resp.ai_findings.map(
      (f): AnnotatedValidationFinding => ({ ...f, source: 'ai' }),
    ),
  ]
  findings.value = extended
  aiSkippedReason.value = resp.ai_skipped_reason ?? null
  lastRunAt.value = resp.run_at
  emitFindingsCount()
}

function _findingKey(
  finding: AnnotatedValidationFinding,
): string {
  return `${finding.source}|${finding.code}|${finding.location || ''}`
}

function runStructuralOnly() {
  return runValidation(false)
}

function runAiOnly() {
  return runValidation(true)
}

async function runAllValidations() {
  if (isRunning.value) return
  isRunning.value = true
  try {
    const structural: ValidationRunResponse =
      await adventureService.runValidation(props.templateId, false)
    mergeValidationResponse(structural)
    try {
      const ai: ValidationRunResponse =
        await adventureService.runValidation(props.templateId, true)
      mergeValidationResponse(ai)
      if (ai.ai_findings.length === 0 && ai.ai_skipped_reason === null) {
        emit('notify', 'AI validation finished with no findings.', 'success')
      }
    } catch (err: any) {
      emit(
        'notify',
        err?.message || 'AI validation failed; structural pass still completed.',
        'error',
      )
    }
  } catch (err: any) {
    emit(
      'notify',
      err?.message || 'Validation failed. See server logs for details.',
      'error',
    )
  } finally {
    isRunning.value = false
  }
}

function clearAll() {
  findings.value = []
  aiSkippedReason.value = null
  lastRunAt.value = null
  emitFindingsCount()
}

function emitFindingsCount() {
  emit(
    'findings-count',
    findings.value.length,
    errorCount.value,
    warningCount.value,
    aiFindingCount.value,
    structuralFindingCount.value,
  )
}

function severityClass(severity: ValidationSeverity): string {
  return severity === 'error'
    ? 'border-rose-500/40 bg-rose-500/5'
    : 'border-amber-500/40 bg-amber-500/5'
}

function severityIcon(severity: ValidationSeverity): string {
  return severity === 'error' ? 'ra ra-skull' : 'ra ra-warning-sign'
}

function severityColor(severity: ValidationSeverity): string {
  return severity === 'error' ? 'text-rose-400' : 'text-amber-400'
}

function sourceLabel(source: 'structural' | 'ai'): string {
  return source === 'ai' ? 'AI' : 'Structural'
}

function sourceClass(source: 'structural' | 'ai'): string {
  return source === 'ai'
    ? 'bg-violet-500/15 text-violet-300 border-violet-500/30'
    : 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
}

function aiSkippedMessage(reason: ValidationAiSkippedReason): string {
  switch (reason) {
    case 'scene_limit_exceeded':
      return 'AI validation was skipped: this adventure is too large for the AI model. Run the structural pass instead.'
    case 'ai_error':
      return 'AI validation failed. Check server logs for details.'
    case 'ai_not_requested':
      return ''
    default:
      return ''
  }
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString()
  } catch {
    return ''
  }
}

function escapeMarkdown(value: string): string {
  return value.replace(/[\\|`*_{}[\]<>]/g, (ch) => '\\' + ch)
}

function buildMarkdown() {
  const title = (props.adventureTitle ?? '').trim() || 'Adventure'
  const safeTitle = title.replace(/[^A-Za-z0-9_-]+/g, '_').slice(0, 60) || 'adventure'
  const runAt = lastRunAt.value ? new Date(lastRunAt.value) : new Date()
  const stamp = runAt.toISOString().replace(/[:.]/g, '-').slice(0, 19)

  const lines: string[] = []
  lines.push(`# Validation Report \u2014 ${title}`)
  lines.push('')
  lines.push(`- Adventure ID: \`${props.templateId}\``)
  lines.push(`- Generated: ${runAt.toISOString()}`)
  lines.push(`- Total findings: **${findings.value.length}** `
    + `(${errorCount.value} errors, ${warningCount.value} warnings)`)
  lines.push('')

  const errors = findings.value.filter((f) => f.severity === 'error')
  const warnings = findings.value.filter((f) => f.severity === 'warn')

  lines.push('## Summary')
  lines.push('')
  lines.push('| Severity | Count |')
  lines.push('| --- | ---: |')
  lines.push(`| \ud83d\udd34 Error | ${errors.length} |`)
  lines.push(`| \ud83d\udfe1 Warning | ${warnings.length} |`)
  lines.push('')

  const groups: Array<{ title: string; items: AnnotatedValidationFinding[] }> = []
  if (errors.length) groups.push({ title: 'Errors', items: errors })
  if (warnings.length) groups.push({ title: 'Warnings', items: warnings })

  for (const group of groups) {
    lines.push(`## ${group.title}`)
    lines.push('')
    for (const finding of group.items) {
      const emoji = finding.severity === 'error' ? '\ud83d\udd34' : '\ud83d\udfe1'
      const code = finding.code
      const source = finding.source === 'ai' ? 'AI logic check' : 'Structural check'
      const location = finding.location ? ` \u2014 \`${escapeMarkdown(finding.location)}\`` : ''
      lines.push(`### ${emoji} \`${code}\`${location}`)
      lines.push('')
      lines.push(`- Source: ${source}`)
      lines.push(`- Severity: ${finding.severity}`)
      lines.push('')
      lines.push(escapeMarkdown(finding.message))
      lines.push('')
      if (finding.context && Object.keys(finding.context).length > 0) {
        lines.push('<details><summary>Context</summary>')
        lines.push('')
        lines.push('```json')
        lines.push(JSON.stringify(finding.context, null, 2))
        lines.push('```')
        lines.push('')
        lines.push('</details>')
        lines.push('')
      }
    }
  }

  if (findings.value.length === 0) {
    lines.push('_No issues found. The adventure passes both structural and AI checks._')
    lines.push('')
  }

  return { markdown: lines.join('\n'), filename: `${safeTitle}-validation-${stamp}.md` }
}

function exportMarkdown() {
  if (findings.value.length === 0) {
    emit('notify', 'Nothing to export \u2014 run a validation first.', 'info')
    return
  }
  const { markdown, filename } = buildMarkdown()
  try {
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    emit('notify', `Exported ${findings.value.length} finding(s) to ${filename}.`, 'success')
  } catch (err: any) {
    emit('notify', err?.message || 'Failed to export validation report.', 'error')
  }
}

// ---------------------------------------------------------------------------
// AI fix suggestions
// ---------------------------------------------------------------------------

const aiFixModalOpen = ref(false)
const aiFixLoading = ref(false)
const aiFixApplying = ref(false)
const aiFixProposals = ref<FixProposal[]>([])
const aiFixSelectedIndex = ref<number>(0)
const aiFixFindingSignature = ref<string>('')
const aiFixFinding = ref<AnnotatedValidationFinding | null>(null)
const aiFixBackupConfirmed = ref(false)
const aiFixErrorMessage = ref<string | null>(null)

function findingKey(finding: AnnotatedValidationFinding, index: number): string {
  return `${finding.source}-${finding.code}-${finding.location || ''}-${index}`
}

async function openAIFixSuggestions(
  finding: AnnotatedValidationFinding,
  index: number,
) {
  if (aiFixLoading.value || aiFixApplying.value) return
  aiFixFinding.value = finding
  aiFixProposals.value = []
  aiFixSelectedIndex.value = 0
  aiFixBackupConfirmed.value = false
  aiFixFindingSignature.value = ''
  aiFixErrorMessage.value = null
  aiFixModalOpen.value = true
  await runAIFixRequest(finding)

  // unused param avoidance
  void findingKey
  void index
}

async function runAIFixRequest(finding: AnnotatedValidationFinding) {
  aiFixLoading.value = true
  aiFixErrorMessage.value = null
  try {
    const request: AIFixSuggestionsRequest = {
      finding_code: finding.code,
      finding_message: finding.message,
      finding_location: finding.location ?? null,
      finding_context: (finding.context ?? null) as Record<string, any> | null,
      finding_severity: finding.severity,
    }
    const resp: AIFixSuggestionsResponse =
      await adventureService.requestAIFixSuggestions(props.templateId, request)
    aiFixProposals.value = resp.proposals ?? []
    aiFixFindingSignature.value = resp.finding_signature
    aiFixErrorMessage.value = resp.error ?? null
    if (aiFixSelectedIndex.value >= aiFixProposals.value.length) {
      aiFixSelectedIndex.value = aiFixProposals.value.length > 0 ? 0 : -1
    }
  } catch (err: any) {
    aiFixErrorMessage.value =
      err?.message || 'AI fix suggestions failed. See server logs for details.'
    emit(
      'notify',
      aiFixErrorMessage.value ?? '',
      'error',
    )
  } finally {
    aiFixLoading.value = false
  }
}

function retryAIFix() {
  if (!aiFixFinding.value || aiFixLoading.value || aiFixApplying.value) return
  aiFixProposals.value = []
  aiFixSelectedIndex.value = 0
  void runAIFixRequest(aiFixFinding.value)
}

function selectFixProposal(index: number) {
  aiFixSelectedIndex.value = index
}

function toggleBackupConfirmation(checked: boolean) {
  aiFixBackupConfirmed.value = checked
}

async function applySelectedFix() {
  const proposal = aiFixProposals.value[aiFixSelectedIndex.value]
  if (!proposal) return
  if (!aiFixBackupConfirmed.value) {
    emit('notify', 'Please confirm you made a backup first.', 'error')
    return
  }
  aiFixApplying.value = true
  aiFixErrorMessage.value = null
  try {
    const resp = await adventureService.applyAIFix(props.templateId, {
      finding_signature: aiFixFindingSignature.value,
      proposal,
    })
    if (resp.status === 'applied' || resp.status === 'partial') {
      emit(
        'notify',
        resp.message ||
          `AI fix applied to ${resp.applied_targets.length} target(s).`,
        resp.status === 'applied' ? 'success' : 'info',
      )
      aiFixModalOpen.value = false
      removeAppliedFinding()
    } else {
      aiFixErrorMessage.value =
        resp.message ||
        'No changes were applied. The AI reference is out of date — please retry to regenerate suggestions.'
    }
  } catch (err: any) {
    aiFixErrorMessage.value =
      err?.message ||
      'Failed to apply AI fix. See server logs for details.'
  } finally {
    aiFixApplying.value = false
  }
}

function removeAppliedFinding() {
  const target = aiFixFinding.value
  if (!target) return
  const targetKey = `${target.source}|${target.code}|${target.location || ''}`
  const before = findings.value.length
  findings.value = findings.value.filter((f) => _findingKey(f) !== targetKey)
  if (findings.value.length !== before) {
    emitFindingsCount()
  }
}

function closeAIFixModal() {
  if (aiFixApplying.value) return
  aiFixModalOpen.value = false
}

onMounted(async () => {
  if (hasAutoRun.value) {
    emitFindingsCount()
    return
  }
  hasAutoRun.value = true

  isHydrating.value = true
  try {
    const persisted = await adventureService.getLatestValidation(props.templateId)
    if (persisted) {
      applyPersistedRun(persisted)
    }
  } catch (err: any) {
    emit(
      'notify',
      err?.message || 'Failed to load the latest validation snapshot.',
      'info',
    )
  } finally {
    isHydrating.value = false
  }

  if (findings.value.length === 0) {
    await runStructuralOnly()
  }
})

function applyPersistedRun(run: PersistedValidationRun) {
  const extended: AnnotatedValidationFinding[] = [
    ...((run.structural_findings ?? []) as ValidationFinding[]).map(
      (f): AnnotatedValidationFinding => ({ ...f, source: 'structural' }),
    ),
    ...((run.ai_findings ?? []) as ValidationFinding[]).map(
      (f): AnnotatedValidationFinding => ({ ...f, source: 'ai' }),
    ),
  ]
  findings.value = extended
  aiSkippedReason.value = (run.ai_skipped_reason ?? null) as ValidationAiSkippedReason
  lastRunAt.value = run.run_at ?? null
  emitFindingsCount()
}

defineExpose({
  runStructuralOnly,
})
</script>

<template>
  <div class="space-y-6 animate-page-in">
    <div class="p-6 bg-slate-900/50 border border-white/5 rounded-3xl space-y-5">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="space-y-1 min-w-0">
          <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
            <ShieldCheck class="w-4 h-4 text-rose-400" />
            Validation
          </h4>
          <p class="text-xs text-slate-400 leading-relaxed">
            Inspect this adventure for structural issues and, optionally, AI-detected inconsistencies.
          </p>
        </div>
        <div class="flex items-center gap-2">
          <span
            v-if="errorCount > 0"
            class="px-3 py-1 rounded-full bg-rose-500/15 border border-rose-500/40 text-rose-300 text-[10px] font-black uppercase tracking-widest"
          >
            {{ errorCount }} error{{ errorCount === 1 ? '' : 's' }}
          </span>
          <span
            v-if="warningCount > 0"
            class="px-3 py-1 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-300 text-[10px] font-black uppercase tracking-widest"
          >
            {{ warningCount }} warning{{ warningCount === 1 ? '' : 's' }}
          </span>
          <span
            v-if="lastRunAt"
            class="text-[10px] text-slate-500 uppercase tracking-widest"
          >
            Last run {{ formatTimestamp(lastRunAt) }}
          </span>
        </div>
      </div>

      <div class="grid sm:grid-cols-3 gap-3">
        <button
          id="btn-run-all-validation"
          type="button"
          :disabled="isRunning"
          @click="runAllValidations"
          class="px-5 py-4 bg-rose-600 hover:bg-rose-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-rose-900/30"
        >
          <ShieldCheck class="w-4 h-4" />
          <span>Validate all</span>
        </button>
        <button
          id="btn-run-ai-validation"
          type="button"
          :disabled="isRunning"
          @click="runAiOnly"
          class="px-5 py-4 bg-violet-600 hover:bg-violet-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-900/30"
        >
          <Sparkles class="w-4 h-4" />
          <span>AI-Validation</span>
        </button>
        <button
          id="btn-run-structural-validation"
          type="button"
          :disabled="isRunning"
          @click="runStructuralOnly"
          class="px-5 py-4 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-900/30"
        >
          <Bug class="w-4 h-4" />
          <span>Structural validation</span>
        </button>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <button
          id="btn-clear-validation"
          type="button"
          :disabled="isRunning || findings.length === 0"
          @click="clearAll"
          class="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 disabled:cursor-not-allowed text-slate-200 text-[11px] font-black uppercase tracking-widest rounded-xl transition-all flex items-center gap-2"
        >
          <Eraser class="w-3.5 h-3.5" />
          <span>Clear all</span>
        </button>
        <button
          id="btn-export-markdown"
          type="button"
          :disabled="isRunning || findings.length === 0"
          @click="exportMarkdown"
          class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-900 disabled:text-slate-600 disabled:cursor-not-allowed text-white text-[11px] font-black uppercase tracking-widest rounded-xl transition-all flex items-center gap-2"
          title="Download all current findings as a Markdown file"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Export MD</span>
        </button>
        <div v-if="isRunning" class="text-[10px] text-slate-500 uppercase tracking-widest flex items-center gap-2">
          <Loader2 class="w-3 h-3 animate-spin" /> Running&hellip;
        </div>
      </div>

      <div
        v-if="aiSkippedMessage(aiSkippedReason)"
        class="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 flex items-start gap-2"
      >
        <ShieldCheck class="w-4 h-4 text-amber-300 shrink-0 mt-0.5" />
        {{ aiSkippedMessage(aiSkippedReason) }}
      </div>

      <div
        v-if="isHydrating"
        class="text-[10px] text-slate-500 uppercase tracking-widest flex items-center gap-2"
      >
        <Loader2 class="w-3 h-3 animate-spin" /> Loading last validation&hellip;
      </div>
    </div>

    <div v-if="findings.length > 0" class="flex items-center gap-2 flex-wrap">
      <button
        v-for="opt in [
          { key: 'all', label: `All (${findings.length})` },
          { key: 'errors', label: `Errors (${errorCount})` },
          { key: 'warnings', label: `Warnings (${warningCount})` },
          { key: 'structural', label: `Structural (${structuralFindingCount})` },
          { key: 'ai', label: `AI (${aiFindingCount})` },
        ]"
        :key="opt.key"
        type="button"
        @click="activeFilter = opt.key as FilterKey"
        :class="[
          'px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border',
          activeFilter === opt.key
            ? 'bg-white/10 text-white border-white/20'
            : 'bg-transparent text-slate-400 border-white/5 hover:border-white/10',
        ]"
      >
        {{ opt.label }}
      </button>
    </div>

    <div v-if="filteredFindings.length > 0" class="space-y-3">
      <div
        v-for="(finding, idx) in filteredFindings"
        :key="findingKey(finding, idx)"
        :class="['p-4 border rounded-2xl flex items-start gap-4', severityClass(finding.severity)]"
      >
        <i :class="[severityIcon(finding.severity), severityColor(finding.severity), 'text-lg mt-0.5']"></i>
        <div class="flex-1 min-w-0 space-y-2">
          <div class="flex items-center gap-2 flex-wrap">
            <span :class="['px-2 py-0.5 rounded-md border text-[10px] font-black uppercase tracking-widest', sourceClass(finding.source)]">
              {{ sourceLabel(finding.source) }}
            </span>
            <code class="text-[11px] font-mono text-slate-400">{{ finding.code }}</code>
            <span
              v-if="finding.location"
              class="text-[10px] text-slate-500 font-mono"
            >
              {{ finding.location }}
            </span>
          </div>
          <p class="text-sm text-slate-200 leading-relaxed">{{ finding.message }}</p>

          <div
            v-if="finding.source === 'ai'"
            class="flex items-center gap-2 pt-1"
          >
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg border border-violet-500/40 bg-violet-500/15 text-violet-200 text-[10px] font-black uppercase tracking-widest hover:bg-violet-500/25 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isRunning || aiFixLoading || aiFixApplying"
              @click="openAIFixSuggestions(finding, idx)"
            >
              <Wand2 class="w-3 h-3" />
              <span>AI-Fix</span>
            </button>
            <span class="text-[10px] text-slate-500 leading-snug">
              Generate up to 3 fix proposals and apply one.
            </span>
          </div>
        </div>
        <button
          type="button"
          class="text-slate-500 hover:text-slate-200 transition-colors p-1"
          title="Dismiss"
          aria-label="Dismiss finding"
          @click="() => { findings.splice(findings.indexOf(finding), 1); emitFindingsCount(); }"
        >
          <i class="ra ra-crossed-swords"></i>
        </button>
      </div>
    </div>

    <div
      v-else-if="!isRunning && findings.length === 0"
      class="p-12 bg-slate-900/50 border border-white/5 rounded-3xl text-center space-y-3"
    >
      <ShieldCheck class="w-10 h-10 mx-auto text-emerald-400" />
      <h5 class="text-sm font-black text-white uppercase tracking-widest">
        All clear
      </h5>
      <p class="text-xs text-slate-400 max-w-md mx-auto">
        No validation findings. Run a check above to refresh; the editor also runs the structural pass
        automatically after each save.
      </p>
    </div>

    <div
      v-else-if="!isRunning && filteredFindings.length === 0 && findings.length > 0"
      class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl text-center text-xs text-slate-500"
    >
      No findings match the current filter.
    </div>

    <AIFixSuggestionsModal
      :open="aiFixModalOpen"
      :proposals="aiFixProposals"
      :loading="aiFixLoading"
      :applying="aiFixApplying"
      :selected-index="aiFixSelectedIndex"
      :finding-code="aiFixFinding?.code ?? ''"
      :finding-message="aiFixFinding?.message ?? ''"
      :finding-location="aiFixFinding?.location ?? null"
      :has-backup-confirmed="aiFixBackupConfirmed"
      :error-message="aiFixErrorMessage"
      @close="closeAIFixModal"
      @select="selectFixProposal"
      @apply="applySelectedFix"
      @toggle-backup="toggleBackupConfirmation"
      @retry="retryAIFix"
    />
  </div>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
