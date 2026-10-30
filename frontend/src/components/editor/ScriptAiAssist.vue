<script setup lang="ts">
/**
 * AI buttons of the script editor: "AI Optimize" improves/fixes the current code and fills
 * placeholder comments, "AI Generate" writes code from a prompt. The proposal is shown as a
 * line diff; nothing changes until the author accepts it.
 */
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { AlertTriangle, Check, LoaderCircle, Wand, WandSparkles, X } from 'lucide-vue-next'
import {
  SCRIPT_ASSIST_INSTRUCTION_MAX,
  scriptAssistService,
  type ScriptAssistMode,
  type ScriptAssistResponse,
} from '@/services/scriptAssistService'
import { diffLines, diffStats } from '@/utils/lineDiff'

const props = defineProps<{
  code: string
  context: string
  label?: string
  disabled?: boolean
}>()

const emit = defineEmits<{ (e: 'apply', code: string): void }>()

const route = useRoute()
const adventureId = computed(() => String(route.params.adventureId || ''))

const loadingMode = ref<ScriptAssistMode | null>(null)
const showPrompt = ref(false)
const instruction = ref('')
const errorMessage = ref('')
const proposal = ref<ScriptAssistResponse | null>(null)
// The code the proposal was made for; the diff compares against it.
const baseCode = ref('')

const diff = computed(() => (proposal.value?.code != null ? diffLines(baseCode.value, proposal.value.code) : []))
const stats = computed(() => diffStats(diff.value))
const isUnchanged = computed(() => proposal.value?.code === baseCode.value)

async function request(mode: ScriptAssistMode) {
  if (!adventureId.value || loadingMode.value) return
  loadingMode.value = mode
  errorMessage.value = ''
  baseCode.value = props.code || ''
  try {
    const result = await scriptAssistService.requestProposal(adventureId.value, {
      mode,
      code: baseCode.value,
      instruction: mode === 'generate' ? instruction.value.trim() : '',
      context: props.context,
      label: props.label,
    })
    if (result.error || result.code == null) {
      errorMessage.value = result.error || 'The AI did not return any code.'
      return
    }
    proposal.value = result
    showPrompt.value = false
  } catch (err: any) {
    errorMessage.value = err?.message || 'The AI request failed.'
  } finally {
    loadingMode.value = null
  }
}

function accept() {
  if (proposal.value?.code != null) emit('apply', proposal.value.code)
  proposal.value = null
}

function discard() {
  proposal.value = null
}
</script>

<template>
  <div v-if="adventureId" class="relative flex items-center gap-1.5">
    <button
      type="button"
      :disabled="disabled || !!loadingMode || !code.trim()"
      class="flex items-center gap-1 px-2 py-1 rounded-lg bg-violet-600/80 hover:bg-violet-500 text-[11px] font-bold text-white transition-colors disabled:opacity-40"
      title="Let the AI fix and improve this code and replace placeholder comments with code"
      @click="request('optimize')"
    >
      <LoaderCircle v-if="loadingMode === 'optimize'" class="w-3 h-3 animate-spin" />
      <Wand v-else class="w-3 h-3" />
      <span class="hidden md:inline">AI Optimize</span>
    </button>
    <button
      type="button"
      :disabled="disabled || !!loadingMode"
      :class="[
        'flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-bold border transition-colors disabled:opacity-40',
        showPrompt
          ? 'bg-violet-500/20 text-violet-200 border-violet-500/40'
          : 'bg-slate-800/80 hover:bg-slate-700 text-slate-300 border-white/5',
      ]"
      title="Describe what the code should do and let the AI write it"
      @click="showPrompt = !showPrompt; errorMessage = ''"
    >
      <LoaderCircle v-if="loadingMode === 'generate'" class="w-3 h-3 animate-spin" />
      <WandSparkles v-else class="w-3 h-3 text-violet-300" />
      <span class="hidden md:inline">AI Generate</span>
    </button>

    <!-- Prompt popover -->
    <div
      v-if="showPrompt"
      class="absolute right-0 top-full mt-1 w-80 p-3 bg-slate-900 border border-violet-500/30 rounded-xl shadow-2xl z-50 space-y-2"
    >
      <textarea
        v-model="instruction"
        rows="3"
        :maxlength="SCRIPT_ASSIST_INSTRUCTION_MAX"
        :disabled="!!loadingMode"
        placeholder="e.g. &quot;Every NPC in the scene gets angry and says what they think about the player&quot;"
        class="w-full resize-y rounded-lg bg-slate-950/70 border border-white/10 focus:border-violet-500/50 focus:outline-none px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600"
        @keydown.ctrl.enter.prevent="request('generate')"
      />
      <div class="flex items-center justify-between gap-2">
        <span class="text-[10px] text-slate-500">Builds on the current code. Ctrl+Enter</span>
        <button
          type="button"
          :disabled="!!loadingMode || !instruction.trim()"
          class="flex items-center gap-1 px-3 py-1 rounded-lg bg-violet-600 hover:bg-violet-500 text-[11px] font-bold text-white disabled:opacity-40"
          @click="request('generate')"
        >
          <LoaderCircle v-if="loadingMode === 'generate'" class="w-3 h-3 animate-spin" />
          {{ loadingMode === 'generate' ? 'Generating...' : 'Generate' }}
        </button>
      </div>
    </div>

    <!-- Error -->
    <div
      v-if="errorMessage"
      class="absolute right-0 top-full mt-1 w-72 p-2.5 bg-rose-950/95 border border-rose-500/30 rounded-xl shadow-2xl z-50 flex items-start gap-2 text-[11px] text-rose-200"
      :class="{ 'mt-36': showPrompt }"
    >
      <AlertTriangle class="w-3.5 h-3.5 shrink-0 mt-0.5" />
      <span class="flex-1">{{ errorMessage }}</span>
      <button type="button" class="text-rose-300 hover:text-white" title="Dismiss" @click="errorMessage = ''">
        <X class="w-3 h-3" />
      </button>
    </div>

    <!-- Diff dialog -->
    <Teleport to="body">
      <div
        v-if="proposal"
        class="fixed inset-0 z-[320] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4"
        role="dialog"
        aria-modal="true"
        aria-label="AI script proposal"
        @click.self="discard"
      >
        <div class="w-full max-w-3xl rounded-2xl border border-violet-500/30 bg-slate-900 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
          <div class="px-5 py-4 border-b border-white/10 flex items-start justify-between gap-4 shrink-0">
            <div class="min-w-0">
              <h3 class="text-sm font-black uppercase tracking-widest text-violet-200">AI proposal</h3>
              <p v-if="proposal.summary" class="text-xs text-slate-300 mt-1">{{ proposal.summary }}</p>
              <p class="text-[11px] font-mono mt-1.5">
                <span class="text-emerald-400">+{{ stats.added }}</span>
                <span class="text-rose-400 ml-2">-{{ stats.removed }}</span>
                <span v-if="isUnchanged" class="text-slate-500 ml-2">no changes</span>
              </p>
            </div>
            <button type="button" class="text-slate-400 hover:text-white" title="Discard" @click="discard">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div
            v-if="proposal.syntax_errors.length"
            class="mx-5 mt-4 p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 text-[11px] text-amber-200 space-y-1"
          >
            <div class="flex items-center gap-1.5 font-bold">
              <AlertTriangle class="w-3.5 h-3.5" /> The proposal still fails the sandbox check:
            </div>
            <div v-for="(err, idx) in proposal.syntax_errors" :key="idx" class="font-mono">{{ err }}</div>
          </div>

          <div class="flex-1 overflow-auto m-5 rounded-xl border border-white/10 bg-slate-950 font-mono text-xs">
            <div
              v-for="(line, idx) in diff"
              :key="idx"
              :class="[
                'flex whitespace-pre',
                line.type === 'add' && 'bg-emerald-500/10 text-emerald-200',
                line.type === 'del' && 'bg-rose-500/10 text-rose-200 line-through decoration-rose-500/40',
                line.type === 'same' && 'text-slate-400',
              ]"
            >
              <span class="w-8 shrink-0 text-right pr-2 text-slate-600 select-none">{{ line.oldNo ?? '' }}</span>
              <span class="w-8 shrink-0 text-right pr-2 text-slate-600 select-none">{{ line.newNo ?? '' }}</span>
              <span class="w-4 shrink-0 select-none">{{ line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' ' }}</span>
              <span class="pr-4">{{ line.text || ' ' }}</span>
            </div>
          </div>

          <div class="px-5 py-4 border-t border-white/10 flex items-center justify-end gap-2 shrink-0">
            <button
              type="button"
              class="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-300"
              @click="discard"
            >
              Discard
            </button>
            <button
              type="button"
              :disabled="isUnchanged"
              class="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white disabled:opacity-40"
              @click="accept"
            >
              <Check class="w-3.5 h-3.5" /> Accept
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
