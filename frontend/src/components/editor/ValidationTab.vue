<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  adventureService,
  type AnnotatedValidationFinding,
  type ValidationAiSkippedReason,
  type ValidationRunResponse,
  type ValidationSeverity,
} from '@/services/adventureService'

type FilterKey = 'all' | 'errors' | 'warnings' | 'structural' | 'ai'

const props = defineProps<{
  templateId: string
  adventureTitle?: string
}>()

const emit = defineEmits<{
  (e: 'notify', message: string, type: 'error' | 'success' | 'info'): void
}>()

const findings = ref<AnnotatedValidationFinding[]>([])
const aiSkippedReason = ref<ValidationAiSkippedReason>(null)
const lastRunAt = ref<string | null>(null)
const isRunning = ref(false)
const activeFilter = ref<FilterKey>('all')
const hasAutoRun = ref(false)

const errorCount = computed(
  () => findings.value.filter((f) => f.severity === 'error').length,
)
const warningCount = computed(
  () => findings.value.filter((f) => f.severity === 'warn').length,
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

function runStructuralOnly() {
  return runValidation(false)
}

function runFullValidation() {
  return runValidation(true)
}

function clearAll() {
  findings.value = []
  aiSkippedReason.value = null
  lastRunAt.value = null
}

function dismiss(index: number) {
  findings.value.splice(index, 1)
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
  // Escape characters that have special meaning in Markdown tables / code spans
  // so that user-supplied content never breaks the document structure.
  return value.replace(/[\\|`*_{}[\]<>]/g, (ch) => '\\' + ch)
}

function buildMarkdown() {
  const title = (props.adventureTitle ?? '').trim() || 'Adventure'
  const safeTitle = title.replace(/[^A-Za-z0-9_-]+/g, '_').slice(0, 60) || 'adventure'
  const runAt = lastRunAt.value ? new Date(lastRunAt.value) : new Date()
  const stamp = runAt.toISOString().replace(/[:.]/g, '-').slice(0, 19) // 2026-06-29T12-34-56

  const lines: string[] = []
  lines.push(`# Validation Report — ${title}`)
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
  lines.push(`| 🔴 Error | ${errors.length} |`)
  lines.push(`| 🟡 Warning | ${warnings.length} |`)
  lines.push('')

  const groups: Array<{ title: string; items: AnnotatedValidationFinding[] }> = []
  if (errors.length) groups.push({ title: 'Errors', items: errors })
  if (warnings.length) groups.push({ title: 'Warnings', items: warnings })

  for (const group of groups) {
    lines.push(`## ${group.title}`)
    lines.push('')
    for (const finding of group.items) {
      const emoji = finding.severity === 'error' ? '🔴' : '🟡'
      const code = finding.code
      const source = finding.source === 'ai' ? 'AI logic check' : 'Structural check'
      const location = finding.location ? ` — \`${escapeMarkdown(finding.location)}\`` : ''
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
    emit('notify', 'Nothing to export — run a validation first.', 'info')
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
    // Revoke after a short delay so the browser has time to start the download.
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    emit('notify', `Exported ${findings.value.length} finding(s) to ${filename}.`, 'success')
  } catch (err: any) {
    emit('notify', err?.message || 'Failed to export validation report.', 'error')
  }
}

onMounted(async () => {
  if (!hasAutoRun.value && findings.value.length === 0) {
    hasAutoRun.value = true
    await runStructuralOnly()
  }
})

defineExpose({
  runStructuralOnly,
})
</script>

<template>
  <div class="space-y-6 animate-page-in">
    <!-- Header card with stats and actions -->
    <div class="p-6 bg-slate-900/50 border border-white/5 rounded-3xl space-y-5">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="space-y-1 min-w-0">
          <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
            <i class="ra ra-gavel text-rose-500"></i> Validation
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

      <div class="flex flex-wrap items-center gap-3">
        <button
          id="btn-run-full-validation"
          type="button"
          :disabled="isRunning"
          @click="runFullValidation"
          class="px-5 py-3 bg-rose-600 hover:bg-rose-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center gap-2"
        >
          <i class="ra ra-burning-embers"></i>
          <span>Run full validation</span>
        </button>
        <button
          id="btn-run-structural-validation"
          type="button"
          :disabled="isRunning"
          @click="runStructuralOnly"
          class="px-5 py-3 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center gap-2"
        >
          <i class="ra ra-anvil"></i>
          <span>Structural validations only</span>
        </button>
        <button
          id="btn-clear-validation"
          type="button"
          :disabled="isRunning || findings.length === 0"
          @click="clearAll"
          class="px-5 py-3 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-900 disabled:text-slate-600 disabled:cursor-not-allowed text-slate-200 text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center gap-2"
        >
          <i class="ra ra-broom"></i>
          <span>Clear all</span>
        </button>
        <button
          id="btn-export-markdown"
          type="button"
          :disabled="isRunning || findings.length === 0"
          @click="exportMarkdown"
          class="px-5 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-900 disabled:text-slate-600 disabled:cursor-not-allowed text-white text-xs font-black uppercase tracking-widest rounded-2xl transition-all flex items-center gap-2"
          title="Download all current findings as a Markdown file"
        >
          <i class="ra ra-scroll-quill"></i>
          <span>Export MD</span>
        </button>
        <div v-if="isRunning" class="text-[10px] text-slate-500 uppercase tracking-widest flex items-center gap-2">
          <i class="ra ra-spinner ra-spin"></i> Running…
        </div>
      </div>

      <!-- AI skipped reason banner -->
      <div
        v-if="aiSkippedMessage(aiSkippedReason)"
        class="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200"
      >
        <i class="ra ra-warning-sign mr-2"></i>
        {{ aiSkippedMessage(aiSkippedReason) }}
      </div>
    </div>

    <!-- Filter bar -->
    <div v-if="findings.length > 0" class="flex items-center gap-2 flex-wrap">
      <button
        v-for="opt in [
          { key: 'all', label: 'All' },
          { key: 'errors', label: `Errors (${errorCount})` },
          { key: 'warnings', label: `Warnings (${warningCount})` },
          { key: 'structural', label: 'Structural' },
          { key: 'ai', label: 'AI' },
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

    <!-- Findings list -->
    <div v-if="filteredFindings.length > 0" class="space-y-3">
      <div
        v-for="(finding, idx) in filteredFindings"
        :key="`${finding.source}-${finding.code}-${finding.location || ''}-${idx}`"
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
        </div>
        <button
          type="button"
          @click="dismiss(findings.indexOf(finding))"
          class="text-slate-500 hover:text-slate-200 transition-colors p-1"
          title="Dismiss"
          aria-label="Dismiss finding"
        >
          <i class="ra ra-crossed-swords"></i>
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!isRunning && findings.length === 0"
      class="p-12 bg-slate-900/50 border border-white/5 rounded-3xl text-center space-y-3"
    >
      <i class="ra ra-crown text-4xl text-emerald-400"></i>
      <h5 class="text-sm font-black text-white uppercase tracking-widest">
        All clear
      </h5>
      <p class="text-xs text-slate-400 max-w-md mx-auto">
        No validation findings. Run a check above to refresh; the editor also runs the structural pass
        automatically after each save.
      </p>
    </div>

    <!-- Filtered empty state -->
    <div
      v-else-if="!isRunning && filteredFindings.length === 0 && findings.length > 0"
      class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl text-center text-xs text-slate-500"
    >
      No findings match the current filter.
    </div>
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