<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick, computed } from 'vue'
import {
  loadCodeMirrorAndSkulpt,
  isCodeMirrorAvailable,
  validatePythonSyntaxWithSkulpt,
  runPythonWithSkulpt,
  type SyntaxCheckResult,
  type ScriptRunResult,
} from '@/utils/cdnScriptLoader'
import {
  Play,
  CheckCircle2,
  AlertCircle,
  Maximize2,
  Minimize2,
  Code2,
  HelpCircle,
  Sparkles,
  Trash2,
  Terminal,
  BookOpen,
} from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    modelValue?: string
    label?: string
    helpText?: string
    context?: string
    placeholder?: string
    minHeight?: string
    maxHeight?: string
    disabled?: boolean
    showActions?: boolean
    showRunner?: boolean
  }>(),
  {
    modelValue: '',
    label: '',
    helpText: '',
    context: 'general',
    placeholder: '# Enter Python script here...',
    minHeight: '130px',
    maxHeight: '450px',
    disabled: false,
    showActions: true,
    showRunner: false,
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}>()

const editorEl = ref<HTMLDivElement | null>(null)
const fallbackTextarea = ref<HTMLTextAreaElement | null>(null)
const isCmReady = ref(false)
const isLoadingCdn = ref(true)
const isFullscreen = ref(false)
const cursorPosition = ref({ line: 1, ch: 0 })

// Validation & Run State
const isCheckingSyntax = ref(false)
const syntaxResult = ref<SyntaxCheckResult | null>(null)
const isRunning = ref(false)
const runResult = ref<ScriptRunResult | null>(null)
const showOutputPanel = ref(false)
const showApiDocs = ref(false)

let cmInstance: any = null

// Snippet templates based on trigger context
const availableSnippets = computed(() => {
  const common = [
    {
      label: 'GM Narration (Game Master)',
      code: 'tw.story.show_message("Du nimmst das Stück Schokolade. Vielleicht hilft es beim Überzeugen.")\n',
    },
    {
      label: 'System Notification',
      code: 'tw.system("System notification message.")\n',
    },
    {
      label: 'Modify player stat',
      code: 'hp = tw.player.get_stat("hp", 100)\ntw.player.set_stat("hp", max(0, hp - 10))\n',
    },
    {
      label: 'Add item to inventory',
      code: 'tw.player.add_item("IRON_KEY")\n',
    },
    {
      label: 'Scene attribute',
      code: 'tw.scene.set_attribute("is_visited", True)\n',
    },
    {
      label: 'NPC speech',
      code: 'tw.npcs.say("NPC_ID", "Greetings, traveler!")\n',
    },
    {
      label: 'Move NPC to scene',
      code: 'tw.npcs.move("NPC_ID", "current")\n',
    },
    {
      label: 'Transfer item (NPC)',
      code: '# Drop from NPC into scene:\ntw.npcs.drop_item("NPC_ID", "ITEM_ID")\n# Or give item to NPC:\n# tw.npcs.give_item("NPC_ID", "ITEM_ID")\n',
    },
    {
      label: 'Defeat / Kill NPC',
      code: 'tw.npcs.kill("NPC_ID", drop_inventory=True)\n',
    },
  ]

  if (props.context === 'on_pickup' || props.context === 'on_drop') {
    return [
      {
        label: 'Pickup curse / buff',
        code: 'tw.player.set_stat("strength", tw.player.get_stat("strength", 10) + 2)\ntw.narrate("You feel surging power coursing through your veins.")\n',
      },
      ...common,
    ]
  }

  if (props.context === 'on_defeat') {
    return [
      {
        label: 'Spawn reward on defeat',
        code: 'tw.player.add_item("ANCIENT_AMULET")\ntw.narrate("The foe drops a glowing amulet upon falling.")\n',
      },
      ...common,
    ]
  }

  if (props.context === 'on_enter_scene' || props.context === 'on_protagonist_enters_scene') {
    return [
      {
        label: 'First entrance trigger',
        code: 'if not tw.scene.get_attribute("visited", False):\n    tw.scene.set_attribute("visited", True)\n    tw.narrate("You step into the chamber for the first time.")\n',
      },
      ...common,
    ]
  }

  return common
})

function initCodeMirror() {
  if (!editorEl.value || !isCodeMirrorAvailable()) return

  const CodeMirror = (window as any).CodeMirror

  // Destroy previous if any
  if (cmInstance) {
    const wrapper = cmInstance.getWrapperElement()
    wrapper?.parentNode?.removeChild(wrapper)
    cmInstance = null
  }

  cmInstance = CodeMirror(editorEl.value, {
    value: props.modelValue || '',
    mode: 'python',
    theme: 'material-darker',
    lineNumbers: true,
    tabSize: 4,
    indentUnit: 4,
    indentWithTabs: false,
    matchBrackets: true,
    autoCloseBrackets: true,
    viewportMargin: Infinity,
    readOnly: props.disabled,
    extraKeys: {
      Tab: (cm: any) => {
        cm.replaceSelection('    ', 'end')
      },
    },
  })

  cmInstance.on('change', () => {
    const val = cmInstance.getValue()
    if (val !== props.modelValue) {
      emit('update:modelValue', val)
      emit('change', val)
    }
  })

  cmInstance.on('cursorActivity', () => {
    const cur = cmInstance.getCursor()
    cursorPosition.value = { line: cur.line + 1, ch: cur.ch + 1 }
  })

  isCmReady.value = true
  setupVisibilityObservers()
  nextTick(() => {
    cmInstance?.refresh()
  })
}

let resizeObserver: ResizeObserver | null = null
let intersectionObserver: IntersectionObserver | null = null

function setupVisibilityObservers() {
  if (!editorEl.value) return

  if (typeof ResizeObserver !== 'undefined' && !resizeObserver) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          if (cmInstance) {
            cmInstance.refresh()
          }
        }
      }
    })
    resizeObserver.observe(editorEl.value)
  }

  if (typeof IntersectionObserver !== 'undefined' && !intersectionObserver) {
    intersectionObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && cmInstance) {
          cmInstance.refresh()
        }
      }
    })
    intersectionObserver.observe(editorEl.value)
  }
}

// Watch external modelValue changes
watch(
  () => props.modelValue,
  (newVal) => {
    if (cmInstance) {
      if ((newVal || '') !== cmInstance.getValue()) {
        const cur = cmInstance.getCursor()
        cmInstance.setValue(newVal || '')
        cmInstance.setCursor(cur)
      }
      nextTick(() => {
        cmInstance?.refresh()
      })
    }
  },
  { immediate: true }
)

watch(
  () => props.disabled,
  (val) => {
    cmInstance?.setOption('readOnly', val)
  }
)

watch(
  () => isFullscreen.value,
  () => {
    nextTick(() => {
      cmInstance?.refresh()
      if (cmInstance) cmInstance.focus()
    })
  }
)

function handleFallbackInput(e: Event) {
  const target = e.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
  emit('change', target.value)
}

function insertSnippet(snippetCode: string) {
  if (cmInstance) {
    const doc = cmInstance.getDoc()
    const cursor = doc.getCursor()
    doc.replaceRange(snippetCode, cursor)
    cmInstance.focus()
  } else {
    const current = props.modelValue || ''
    const updated = current ? current + '\n' + snippetCode : snippetCode
    emit('update:modelValue', updated)
    emit('change', updated)
  }
}

function insertNamedSnippet(type: string) {
  const snippets: Record<string, string> = {
    player: 'tw.player.damage(5)\n',
    story: "tw.story.show_message('Du nimmst das Stück Schokolade. Vielleicht hilft es beim Überzeugen.')\n",
    system: "tw.system('System notification message.')\n",
    vars: "tw.vars.set('quest_flag', True)\n",
    scene: "tw.scene.set_attribute('visited', True)\n",
    exits: "tw.exits.unlock('EXIT_ID')\n",
    npcs: "tw.npcs.move('NPC_ID', 'SCENE_ID')\n",
  }
  if (snippets[type]) {
    insertSnippet(snippets[type])
  }
}

function clearScript() {
  if (cmInstance) {
    cmInstance.setValue('')
    cmInstance.focus()
  } else {
    emit('update:modelValue', '')
    emit('change', '')
  }
  syntaxResult.value = null
  runResult.value = null
  showOutputPanel.value = false
}

function handleCheckSyntax() {
  isCheckingSyntax.value = true
  showOutputPanel.value = true
  runResult.value = null
  const code = cmInstance ? cmInstance.getValue() : props.modelValue || ''
  try {
    const res = validatePythonSyntaxWithSkulpt(code)
    syntaxResult.value = res
  } catch (err: any) {
    syntaxResult.value = {
      valid: false,
      error: err.message || 'Syntax parsing failed',
    }
  } finally {
    isCheckingSyntax.value = false
  }
}

async function handleRunScript() {
  isRunning.value = true
  showOutputPanel.value = true
  const code = cmInstance ? cmInstance.getValue() : props.modelValue || ''

  // Validate syntax first
  const syntaxCheck = validatePythonSyntaxWithSkulpt(code)
  syntaxResult.value = syntaxCheck

  if (!syntaxCheck.valid) {
    runResult.value = {
      success: false,
      output: '',
      error: syntaxCheck.error || 'Syntax error detected prior to run.',
    }
    isRunning.value = false
    return
  }

  try {
    const res = await runPythonWithSkulpt(code)
    runResult.value = res
  } catch (err: any) {
    runResult.value = {
      success: false,
      output: '',
      error: err.message || 'Execution error',
    }
  } finally {
    isRunning.value = false
  }
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

onMounted(async () => {
  isLoadingCdn.value = true
  try {
    const { codeMirrorLoaded } = await loadCodeMirrorAndSkulpt()
    if (codeMirrorLoaded) {
      await nextTick()
      initCodeMirror()
    }
  } catch (err) {
    console.warn('[ScriptEditor] Failed to load CDN resources, falling back to textarea', err)
  } finally {
    isLoadingCdn.value = false
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  intersectionObserver?.disconnect()
  intersectionObserver = null
  if (cmInstance) {
    const wrapper = cmInstance.getWrapperElement()
    wrapper?.parentNode?.removeChild(wrapper)
    cmInstance = null
  }
})
</script>

<template>
  <div
    :class="[
      'script-editor-container flex flex-col rounded-xl border border-white/10 bg-slate-950/90 transition-all overflow-hidden',
      isFullscreen ? 'fixed inset-4 z-50 shadow-2xl bg-slate-950 border-amber-500/50' : 'relative',
    ]"
  >
    <!-- Header / Toolbar -->
    <div
      class="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 border-b border-white/5 bg-slate-900/70 select-none"
    >
      <!-- Label & Help -->
      <div class="flex items-center gap-2 min-w-0">
        <div class="flex items-center gap-1.5">
          <Code2 class="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span
            v-if="label"
            class="text-[11px] font-black text-amber-500 uppercase tracking-widest truncate"
          >
            {{ label }}
          </span>
          <span
            class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold"
          >
            PY
          </span>
        </div>

        <div v-if="helpText" class="group relative flex items-center">
          <HelpCircle class="w-3.5 h-3.5 text-slate-500 hover:text-white cursor-help transition-colors" />
          <div
            class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-[10px] text-slate-300 font-normal normal-case tracking-normal rounded-xl shadow-2xl opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-white/10 z-50 space-y-1.5"
          >
            <div>{{ helpText }}</div>
            <div class="text-[9px] text-amber-300 font-mono border-t border-white/10 pt-1">
              📖 Guide: docs/scripting_engine.md
            </div>
          </div>
        </div>

        <!-- Cursor line/col -->
        <span
          v-if="isCmReady"
          class="hidden sm:inline-block text-[10px] font-mono text-slate-500 ml-2"
        >
          Ln {{ cursorPosition.line }}, Col {{ cursorPosition.ch }}
        </span>
      </div>

      <!-- Actions -->
      <div v-if="showActions" class="flex items-center gap-1.5 shrink-0">
        <!-- Scripting Engine Docs (?) Button -->
        <button
          type="button"
          @click="showApiDocs = !showApiDocs"
          :class="[
            'flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-bold border transition-colors',
            showApiDocs
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm'
              : 'bg-slate-800/80 hover:bg-slate-700 text-slate-300 border-white/5',
          ]"
          title="TaleWeaver Scripting Guide & Reference (docs/scripting_engine.md)"
        >
          <BookOpen class="w-3 h-3 text-amber-400" />
          <span class="hidden md:inline">Docs</span>
          <span class="text-amber-400 font-black">?</span>
        </button>

        <!-- Snippets Dropdown -->
        <div class="relative group">
          <button
            type="button"
            class="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-[11px] font-bold text-slate-300 transition-colors border border-white/5"
            title="Insert Code Snippet"
          >
            <Sparkles class="w-3 h-3 text-amber-400" />
            <span class="hidden md:inline">Snippets</span>
          </button>
          <div
            class="absolute right-0 top-full mt-1 w-56 p-1.5 bg-slate-900 border border-white/10 rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 space-y-1"
          >
            <button
              v-for="(snip, idx) in availableSnippets"
              :key="idx"
              type="button"
              @click="insertSnippet(snip.code)"
              class="w-full text-left px-2.5 py-1.5 text-xs text-slate-300 hover:bg-amber-500/10 hover:text-amber-300 rounded-lg transition-colors truncate block"
            >
              {{ snip.label }}
            </button>
          </div>
        </div>

        <!-- Syntax Check (Skulpt) -->
        <button
          type="button"
          @click="handleCheckSyntax"
          :disabled="isCheckingSyntax || !modelValue"
          class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-600/80 hover:bg-emerald-500 text-white text-[11px] font-bold transition-all disabled:opacity-40 shadow-sm"
          title="Verify Python syntax in-browser using Skulpt AST"
        >
          <CheckCircle2 class="w-3.5 h-3.5" />
          <span>{{ isCheckingSyntax ? 'Checking...' : 'Check Syntax' }}</span>
        </button>

        <!-- Optional Test Run (only if explicitly enabled) -->
        <button
          v-if="showRunner"
          type="button"
          @click="handleRunScript"
          :disabled="isRunning || !modelValue"
          class="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-bold transition-all disabled:opacity-40"
          title="Simulate script in browser sandbox"
        >
          <Play class="w-3 h-3 text-emerald-400" />
          <span class="hidden sm:inline">{{ isRunning ? 'Running...' : 'Run' }}</span>
        </button>

        <!-- Clear -->
        <button
          v-if="modelValue"
          type="button"
          @click="clearScript"
          class="p-1 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          title="Clear code"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>

        <!-- Fullscreen Toggle -->
        <button
          type="button"
          @click="toggleFullscreen"
          class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
          :title="isFullscreen ? 'Exit Fullscreen' : 'Expand Fullscreen'"
        >
          <Minimize2 v-if="isFullscreen" class="w-3.5 h-3.5 text-amber-400" />
          <Maximize2 v-else class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- Scripting Guide / API Reference Drawer -->
    <div
      v-if="showApiDocs"
      class="border-b border-white/10 bg-slate-900/95 p-3.5 text-xs space-y-2.5 max-h-72 overflow-y-auto"
    >
      <div class="flex items-center justify-between pb-1.5 border-b border-white/10">
        <div class="flex items-center gap-2">
          <BookOpen class="w-3.5 h-3.5 text-amber-400" />
          <span class="font-bold text-white uppercase tracking-wider text-[11px]">
            TaleWeaver Scripting Guide & Reference
          </span>
          <span class="text-[9px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
            docs/scripting_engine.md
          </span>
        </div>
        <button
          type="button"
          @click="showApiDocs = false"
          class="text-slate-400 hover:text-white text-xs font-bold px-1.5 py-0.5 rounded hover:bg-white/5"
        >
          ✕
        </button>
      </div>

      <p class="text-[11px] text-slate-300 leading-relaxed font-sans">
        Event-driven Python logic executed in a sandboxed turn loop. Full documentation, examples, and safety rules are in
        <code class="text-amber-300 font-mono bg-black/40 px-1.5 py-0.5 rounded border border-white/5">docs/scripting_engine.md</code>
      </p>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 text-[11px] font-mono">
        <div class="p-2 bg-slate-950/70 border border-white/5 rounded-lg space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-400">tw.player</span>
            <button type="button" @click="insertNamedSnippet('player')" class="text-[10px] text-slate-500 hover:text-amber-300 font-sans">Insert</button>
          </div>
          <p class="text-[10px] text-slate-400 font-sans">
            <code>.has_item(id)</code>, <code>.damage(n)</code>, <code>.heal(n)</code>, <code>.set_stat(k, v)</code>
          </p>
        </div>

        <div class="p-2 bg-slate-950/70 border border-white/5 rounded-lg space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-400">tw.story</span>
            <button type="button" @click="insertNamedSnippet('story')" class="text-[10px] text-slate-500 hover:text-amber-300 font-sans">Insert</button>
          </div>
          <p class="text-[10px] text-slate-400 font-sans">
            <code>.show_message(text)</code> (GM Narration), <code>.system(text)</code> (System Note)
          </p>
        </div>

        <div class="p-2 bg-slate-950/70 border border-white/5 rounded-lg space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-400">tw.vars</span>
            <button type="button" @click="insertNamedSnippet('vars')" class="text-[10px] text-slate-500 hover:text-amber-300 font-sans">Insert</button>
          </div>
          <p class="text-[10px] text-slate-400 font-sans">
            <code>.get(k, default)</code>, <code>.set(k, v)</code> (persists across turns)
          </p>
        </div>

        <div class="p-2 bg-slate-950/70 border border-white/5 rounded-lg space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-400">tw.scene</span>
            <button type="button" @click="insertNamedSnippet('scene')" class="text-[10px] text-slate-500 hover:text-amber-300 font-sans">Insert</button>
          </div>
          <p class="text-[10px] text-slate-400 font-sans">
            <code>.id</code>, <code>.name</code>, <code>.get_attribute(k)</code>, <code>.set_attribute(k, v)</code>
          </p>
        </div>

        <div class="p-2 bg-slate-950/70 border border-white/5 rounded-lg space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-400">tw.exits</span>
            <button type="button" @click="insertNamedSnippet('exits')" class="text-[10px] text-slate-500 hover:text-amber-300 font-sans">Insert</button>
          </div>
          <p class="text-[10px] text-slate-400 font-sans">
            <code>.unlock(id)</code>, <code>.lock(id, reason)</code>, <code>.reveal(id)</code>
          </p>
        </div>

        <div class="p-2 bg-slate-950/70 border border-white/5 rounded-lg space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-400">tw.npcs</span>
            <button type="button" @click="insertNamedSnippet('npcs')" class="text-[10px] text-slate-500 hover:text-amber-300 font-sans">Insert</button>
          </div>
          <p class="text-[10px] text-slate-400 font-sans">
            <code>.get(id)</code>, <code>.move(id, target_scene)</code>
          </p>
        </div>
      </div>
    </div>

    <!-- Main Editor Canvas -->
    <div
      class="relative flex-1 min-h-0 bg-slate-950 font-mono text-xs overflow-hidden"
      :style="{ minHeight: isFullscreen ? '400px' : minHeight, maxHeight: isFullscreen ? 'none' : maxHeight }"
    >
      <!-- Loading CDN Spinner / Notice -->
      <div
        v-if="isLoadingCdn && !isCmReady"
        class="absolute inset-0 flex items-center justify-center bg-slate-950/80 z-10 backdrop-blur-sm gap-2 text-slate-400 text-xs"
      >
        <div class="w-3.5 h-3.5 border-2 border-amber-500/30 border-t-amber-500 rounded-full animate-spin"></div>
        <span>Loading Python Editor engine...</span>
      </div>

      <!-- CodeMirror Container -->
      <div
        ref="editorEl"
        v-show="isCmReady"
        class="codemirror-wrapper w-full h-full text-slate-200"
      ></div>

      <!-- Fallback Textarea if CDN is offline or unavailable -->
      <textarea
        v-if="!isCmReady"
        ref="fallbackTextarea"
        :value="modelValue"
        @input="handleFallbackInput"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="5"
        class="w-full h-full p-3 bg-transparent text-emerald-300 font-mono text-xs focus:outline-none resize-y leading-relaxed"
        spellcheck="false"
      ></textarea>
    </div>

    <!-- Output / Results Drawer -->
    <div
      v-if="showOutputPanel && (syntaxResult || runResult)"
      class="border-t border-white/10 bg-slate-900/95 p-3 text-xs font-mono space-y-2 max-h-48 overflow-y-auto"
    >
      <div class="flex items-center justify-between">
        <span class="flex items-center gap-1.5 font-bold uppercase tracking-wider text-[10px] text-slate-400">
          <Terminal class="w-3 h-3 text-amber-400" />
          Syntax Validation Output
        </span>
        <button
          type="button"
          @click="showOutputPanel = false"
          class="text-slate-500 hover:text-white text-[10px]"
        >
          Close [x]
        </button>
      </div>

      <!-- Syntax Check Feedback -->
      <div
        v-if="syntaxResult"
        :class="[
          'p-2 rounded-lg border flex items-start gap-2',
          syntaxResult.valid
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-300',
        ]"
      >
        <CheckCircle2 v-if="syntaxResult.valid" class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
        <AlertCircle v-else class="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
        <div class="text-[11px] leading-tight">
          <span class="font-bold">
            {{ syntaxResult.valid ? 'Python 3 Syntax Validated (Skulpt AST)' : 'Syntax Error' }}
          </span>
          <p v-if="!syntaxResult.valid" class="text-rose-200 mt-1 whitespace-pre-wrap font-mono">
            {{ syntaxResult.error }}
          </p>
        </div>
      </div>

      <!-- Run Result Feedback -->
      <div
        v-if="runResult"
        :class="[
          'p-2 rounded-lg border',
          runResult.success
            ? 'bg-slate-950/80 border-emerald-500/20 text-emerald-200'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-300',
        ]"
      >
        <div class="flex items-center justify-between pb-1 mb-1 border-b border-white/5 text-[10px]">
          <span :class="runResult.success ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'">
            {{ runResult.success ? '✓ Run Simulation Success' : '✕ Simulation Failed' }}
          </span>
        </div>
        <pre class="text-[11px] font-mono text-slate-300 whitespace-pre-wrap leading-relaxed max-h-32 overflow-y-auto">{{ runResult.output }}</pre>
        <p v-if="runResult.error" class="text-rose-400 mt-1 font-bold whitespace-pre-wrap">
          {{ runResult.error }}
        </p>
      </div>
    </div>
  </div>
</template>

<style>
.codemirror-wrapper {
  overflow: hidden;
  height: 100%;
}

/* CodeMirror overrides to integrate with TaleWeaver dark theme */
.codemirror-wrapper .CodeMirror {
  height: 100% !important;
  min-height: 120px;
  background-color: transparent !important;
  color: #e2e8f0 !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
  font-size: 12px !important;
  line-height: 1.6 !important;
  padding: 4px 0;
}

.codemirror-wrapper .CodeMirror-scroll {
  height: 100% !important;
  overflow-x: auto !important;
  overflow-y: auto !important;
}

.codemirror-wrapper .CodeMirror-gutters {
  background-color: rgba(6, 9, 17, 0.7) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
  padding-right: 4px;
}

.codemirror-wrapper .CodeMirror-linenumber {
  color: #475569 !important;
  font-size: 11px;
}

.codemirror-wrapper .CodeMirror-cursor {
  border-left: 2px solid #10b981 !important;
}

.codemirror-wrapper .CodeMirror-selected {
  background-color: rgba(52, 211, 153, 0.2) !important;
}

.codemirror-wrapper .cm-keyword {
  color: #fbbf24 !important; /* amber-400 */
  font-weight: bold;
}

.codemirror-wrapper .cm-string {
  color: #34d399 !important; /* emerald-400 */
}

.codemirror-wrapper .cm-number {
  color: #38bdf8 !important; /* sky-400 */
}

.codemirror-wrapper .cm-comment {
  color: #64748b !important; /* slate-500 */
  font-style: italic;
}

.codemirror-wrapper .cm-variable {
  color: #f1f5f9 !important;
}

.codemirror-wrapper .cm-builtin {
  color: #c084fc !important; /* purple-400 */
}

.codemirror-wrapper .cm-def {
  color: #60a5fa !important; /* blue-400 */
}

.codemirror-wrapper .cm-operator {
  color: #f43f5e !important; /* rose-500 */
}
</style>
