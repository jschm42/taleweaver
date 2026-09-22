<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Code,
  Plus,
  Trash2,
  Edit2,
  Copy,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  X,
  Play,
} from 'lucide-vue-next'
import { adventureService } from '@/services/adventureService'

const props = defineProps<{
  adventure: any
  referenceOptions?: Array<{ id: string; name?: string; imageUrl?: string | null }>
}>()

const emit = defineEmits<{
  (e: 'update-scripts', scripts: any[]): void
  (e: 'notify', message: string, type?: 'error' | 'success' | 'info'): void
}>()

// ---------------------------------------------------------------------------
// Scripts List & Computed State
// ---------------------------------------------------------------------------

const scripts = computed<any[]>(() => {
  const raw = props.adventure?.scripts
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
})

const searchQuery = ref('')
const selectedTriggerFilter = ref('all')

const filteredScripts = computed(() => {
  return scripts.value.filter((script) => {
    const matchesTrigger =
      selectedTriggerFilter.value === 'all' || script.trigger === selectedTriggerFilter.value
    const q = searchQuery.value.toLowerCase().trim()
    if (!q) return matchesTrigger

    const matchesQuery =
      String(script.name || '').toLowerCase().includes(q) ||
      String(script.id || '').toLowerCase().includes(q) ||
      String(script.target || '').toLowerCase().includes(q) ||
      String(script.code || '').toLowerCase().includes(q)

    return matchesTrigger && matchesQuery
  })
})

// ---------------------------------------------------------------------------
// Trigger Colors & Helpers
// ---------------------------------------------------------------------------

const TRIGGER_OPTIONS = [
  { value: 'on_turn_start', label: 'On Turn Start', desc: 'Runs before player prompt and GM logic' },
  { value: 'on_enter_scene', label: 'On Enter Scene', desc: 'Runs when player enters target scene' },
  { value: 'on_interact', label: 'On Interact', desc: 'Runs when interacting with target entity/item' },
  { value: 'on_turn_end', label: 'On Turn End', desc: 'Runs after scene narrative and entity mutations' },
] as const

function getTriggerBadgeClass(trigger: string): string {
  switch (trigger) {
    case 'on_turn_start':
      return 'bg-sky-500/15 text-sky-300 border-sky-500/30'
    case 'on_enter_scene':
      return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    case 'on_interact':
      return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
    case 'on_turn_end':
      return 'bg-purple-500/15 text-purple-300 border-purple-500/30'
    default:
      return 'bg-slate-500/15 text-slate-300 border-slate-500/30'
  }
}

function getTriggerLabel(trigger: string): string {
  const found = TRIGGER_OPTIONS.find((t) => t.value === trigger)
  return found ? found.label : trigger
}

// ---------------------------------------------------------------------------
// Modal & Editor State
// ---------------------------------------------------------------------------

const showModal = ref(false)
const isNewScript = ref(false)
const showDeleteConfirmModal = ref(false)
const pendingDeleteScriptId = ref<string | null>(null)
const isCheckingSyntax = ref(false)
const syntaxValidationResult = ref<{
  checked: boolean
  valid: boolean
  errors: string[]
  warnings: string[]
} | null>(null)
const showApiReference = ref(false)

const modalScript = ref({
  id: '',
  name: '',
  trigger: 'on_turn_start',
  target: '',
  code: '',
  priority: 100,
  is_active: true,
})

function openAddModal() {
  isNewScript.value = true
  syntaxValidationResult.value = null
  showApiReference.value = false
  modalScript.value = {
    id: `script_${Math.random().toString(36).substring(2, 8)}`,
    name: 'New Event Script',
    trigger: 'on_turn_start',
    target: '',
    code: '# Python Script Sandbox\n# tw provides access to player, scene, exits, npcs, vars, etc.\n',
    priority: 100,
    is_active: true,
  }
  showModal.value = true
}

function openEditModal(script: any) {
  isNewScript.value = false
  syntaxValidationResult.value = null
  showApiReference.value = false
  modalScript.value = {
    id: script.id || '',
    name: script.name || '',
    trigger: script.trigger || 'on_turn_start',
    target: script.target || '',
    code: script.code || '',
    priority: script.priority ?? 100,
    is_active: script.is_active !== false,
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  syntaxValidationResult.value = null
}

function duplicateScript(script: any) {
  const newId = `script_${Math.random().toString(36).substring(2, 8)}`
  const cloned = {
    ...script,
    id: newId,
    name: `${script.name || 'Script'} (Copy)`,
  }
  const updated = [...scripts.value, cloned]
  emit('update-scripts', updated)
  emit('notify', `Script duplicated as ${newId}`, 'success')
}

function toggleScriptActive(script: any) {
  const updated = scripts.value.map((s) => {
    if (s.id === script.id) {
      return { ...s, is_active: !s.is_active }
    }
    return s
  })
  emit('update-scripts', updated)
  emit('notify', `Script ${script.name || script.id} ${script.is_active ? 'disabled' : 'enabled'}.`, 'info')
}

function requestDeleteScript(scriptId: string) {
  pendingDeleteScriptId.value = scriptId
  showDeleteConfirmModal.value = true
}

function confirmDeleteScript() {
  if (!pendingDeleteScriptId.value) return
  const updated = scripts.value.filter((s) => s.id !== pendingDeleteScriptId.value)
  emit('update-scripts', updated)
  showDeleteConfirmModal.value = false
  pendingDeleteScriptId.value = null
  emit('notify', 'Script deleted.', 'success')
}

// ---------------------------------------------------------------------------
// Syntax Validation
// ---------------------------------------------------------------------------

async function checkSyntax() {
  if (!props.adventure?.id) return
  isCheckingSyntax.value = true
  syntaxValidationResult.value = null

  try {
    const res = await adventureService.validateScript(props.adventure.id, {
      code: modalScript.value.code,
      trigger: modalScript.value.trigger,
      target: modalScript.value.target || undefined,
    })

    syntaxValidationResult.value = {
      checked: true,
      valid: res.valid,
      errors: res.errors || [],
      warnings: res.warnings || [],
    }

    if (res.valid) {
      emit('notify', 'Syntax and sandbox verification passed!', 'success')
    } else {
      emit('notify', `Found ${res.errors.length} syntax/safety issue(s).`, 'error')
    }
  } catch (err: any) {
    syntaxValidationResult.value = {
      checked: true,
      valid: false,
      errors: [err.message || 'Validation request failed.'],
      warnings: [],
    }
    emit('notify', err.message || 'Validation failed.', 'error')
  } finally {
    isCheckingSyntax.value = false
  }
}

// ---------------------------------------------------------------------------
// Save Script
// ---------------------------------------------------------------------------

async function saveScript() {
  const sId = (modalScript.value.id || '').trim()
  if (!sId) {
    emit('notify', 'Script ID is required.', 'error')
    return
  }

  // Validate ID format
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(sId)) {
    emit('notify', 'Script ID must only contain letters, numbers, underscores, and hyphens.', 'error')
    return
  }

  // Check duplicate ID if new
  if (isNewScript.value && scripts.value.some((s) => s.id === sId)) {
    emit('notify', `A script with ID '${sId}' already exists.`, 'error')
    return
  }

  const scriptEntry = {
    id: sId,
    name: (modalScript.value.name || '').trim() || sId,
    trigger: modalScript.value.trigger,
    target: (modalScript.value.target || '').trim() || null,
    code: modalScript.value.code,
    priority: Number(modalScript.value.priority) || 100,
    is_active: Boolean(modalScript.value.is_active),
  }

  let updated: any[]
  if (isNewScript.value) {
    updated = [...scripts.value, scriptEntry]
  } else {
    updated = scripts.value.map((s) => (s.id === sId ? scriptEntry : s))
  }

  emit('update-scripts', updated)
  closeModal()
  emit('notify', `Script '${scriptEntry.name}' saved successfully.`, 'success')
}

// ---------------------------------------------------------------------------
// Snippet Templates
// ---------------------------------------------------------------------------

const SNIPPET_TEMPLATES = [
  {
    label: 'Story Message',
    code: 'tw.story.show_message("A mysterious chill fills the air as ancient runes glow faintly.")\n',
  },
  {
    label: 'Move NPC',
    code: '# Move an NPC to a specific scene\ntw.npcs.move("NPC_NAME", "SCENE_ID")\n',
  },
  {
    label: 'Lock / Unlock Exit',
    code: '# Lock an exit with reason, or unlock it\ntw.exits.lock("EXIT_ID", "A sturdy iron grate blocks the passage.")\n# tw.exits.unlock("EXIT_ID")\n',
  },
  {
    label: 'Modify Player HP',
    code: '# Damage or heal protagonist avatar\ntw.player.damage(15)\n# tw.player.heal(20)\n',
  },
  {
    label: 'Custom Variable (State)',
    code: '# Check and toggle custom quest/puzzle flags\nif not tw.vars.get("chamber_cleared", False):\n    tw.vars.set("chamber_cleared", True)\n    tw.story.show_message("You hear the sound of stone shifting in the distance.")\n',
  },
  {
    label: 'Add Memory',
    code: '# Inject custom narrative memory into avatar context\ntw.memories.add("Discovered an inscription detailing the moon crest ritual.")\n',
  },
  {
    label: 'Victory / Game Over',
    code: '# Trigger victory or defeat\ntw.game.set_victory("You have retrieved the lost relic and saved the realm!")\n# tw.game.set_game_over("The ancient darkness completely consumed your spirit.")\n',
  },
  {
    label: 'Complete Quest',
    code: '# Mark quest completed\ntw.quests.complete("MAIN_QUEST_ID")\n',
  },
  {
    label: 'Dice Roll Check',
    code: '# Roll a safe die (1 to 20)\nroll = tw.dice.d20()\nif roll >= 12:\n    tw.story.show_message("You skillfully dodge the falling rocks! (Roll: " + str(roll) + ")")\nelse:\n    tw.player.damage(10)\n    tw.story.show_message("A falling boulder grazes your shoulder! (Roll: " + str(roll) + ")")\n',
  },
]

function insertSnippet(code: string) {
  modalScript.value.code = (modalScript.value.code || '').trimEnd() + '\n\n' + code
  syntaxValidationResult.value = null
}

function handleTabKey(e: KeyboardEvent) {
  if (e.key === 'Tab') {
    e.preventDefault()
    const target = e.target as HTMLTextAreaElement
    const start = target.selectionStart
    const end = target.selectionEnd
    modalScript.value.code =
      modalScript.value.code.substring(0, start) + '    ' + modalScript.value.code.substring(end)
    setTimeout(() => {
      target.selectionStart = target.selectionEnd = start + 4
    }, 0)
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Top Header & Controls -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-slate-900/60 border border-white/10 rounded-2xl p-6 backdrop-blur-md">
      <div>
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-950/40">
            <Code class="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 class="text-xl font-black text-white flex items-center gap-2">
              Event Scripts Engine
              <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-bold">
                {{ scripts.length }} {{ scripts.length === 1 ? 'Script' : 'Scripts' }}
              </span>
            </h2>
            <p class="text-xs text-slate-400 mt-0.5">
              Custom Python-syntax logic triggered during turns, scene transitions, and entity interactions.
            </p>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button
          @click="openAddModal"
          class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-black text-xs uppercase tracking-wider shadow-lg shadow-emerald-950/40 transition-all hover:scale-105 active:scale-95"
        >
          <Plus class="w-4 h-4" />
          New Script
        </button>
      </div>
    </div>

    <!-- Filters & Search Bar -->
    <div class="flex flex-col sm:flex-row items-center gap-3">
      <div class="relative flex-1 w-full">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Filter scripts by name, trigger, target, or code..."
          class="w-full bg-slate-900/50 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <button
          v-if="searchQuery"
          @click="searchQuery = ''"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>

      <div class="flex items-center gap-2 w-full sm:w-auto">
        <select
          v-model="selectedTriggerFilter"
          class="w-full sm:w-auto bg-slate-900/50 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-slate-300 focus:outline-none focus:border-emerald-500 transition-colors"
        >
          <option value="all">All Triggers</option>
          <option v-for="opt in TRIGGER_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="filteredScripts.length === 0"
      class="border border-dashed border-white/10 rounded-2xl p-12 text-center bg-slate-900/20"
    >
      <div class="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-4 text-emerald-400">
        <Code class="w-6 h-6" />
      </div>
      <h3 class="text-base font-bold text-white mb-1">
        {{ searchQuery || selectedTriggerFilter !== 'all' ? 'No scripts match your filter' : 'No Event Scripts Yet' }}
      </h3>
      <p class="text-xs text-slate-400 max-w-md mx-auto mb-5">
        {{
          searchQuery || selectedTriggerFilter !== 'all'
            ? 'Try clearing the search query or selecting a different trigger filter.'
            : 'Add custom script triggers to react to turns, player interactions, scene transitions, and manipulate world states.'
        }}
      </p>
      <button
        v-if="!searchQuery && selectedTriggerFilter === 'all'"
        @click="openAddModal"
        class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs uppercase tracking-wider transition-colors"
      >
        <Plus class="w-4 h-4" />
        Create First Script
      </button>
    </div>

    <!-- Scripts Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="script in filteredScripts"
        :key="script.id"
        :class="[
          'relative border rounded-2xl p-5 flex flex-col justify-between transition-all bg-slate-900/40 backdrop-blur-sm group hover:border-emerald-500/40',
          script.is_active !== false ? 'border-white/10' : 'border-white/5 opacity-60'
        ]"
      >
        <div>
          <!-- Header: Title, Active Switch, ID -->
          <div class="flex items-start justify-between gap-3 mb-3">
            <div>
              <h3 class="text-sm font-bold text-white flex items-center gap-2 group-hover:text-emerald-300 transition-colors">
                {{ script.name || script.id }}
                <span
                  v-if="script.is_active === false"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-semibold uppercase"
                >
                  Disabled
                </span>
              </h3>
              <p class="text-[11px] text-slate-500 font-mono mt-0.5">{{ script.id }}</p>
            </div>

            <!-- Priority & Active Toggle -->
            <div class="flex items-center gap-2">
              <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/80 border border-white/10 text-slate-400" title="Execution Priority (lower runs earlier)">
                P: {{ script.priority ?? 100 }}
              </span>

              <button
                @click="toggleScriptActive(script)"
                :class="[
                  'w-8 h-4 rounded-full p-0.5 transition-colors',
                  script.is_active !== false ? 'bg-emerald-500' : 'bg-slate-700'
                ]"
                title="Toggle Active Status"
              >
                <div
                  :class="[
                    'w-3 h-3 rounded-full bg-white transition-transform',
                    script.is_active !== false ? 'translate-x-4' : 'translate-x-0'
                  ]"
                ></div>
              </button>
            </div>
          </div>

          <!-- Tags: Trigger & Target -->
          <div class="flex flex-wrap items-center gap-2 mb-3">
            <span :class="['text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border', getTriggerBadgeClass(script.trigger)]">
              {{ getTriggerLabel(script.trigger) }}
            </span>

            <span
              v-if="script.target"
              class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 border border-white/10 text-slate-300"
            >
              Target: {{ script.target }}
            </span>
          </div>

          <!-- Code Snippet Preview -->
          <div class="bg-slate-950/80 border border-white/5 rounded-xl p-3 font-mono text-[11px] text-slate-300 max-h-24 overflow-hidden relative mb-4 leading-relaxed">
            <pre class="overflow-hidden whitespace-pre-wrap select-none">{{ (script.code || '# (Empty script)').split('\n').slice(0, 4).join('\n') }}</pre>
            <div class="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-slate-950 to-transparent pointer-events-none"></div>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
          <button
            @click="duplicateScript(script)"
            class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
            title="Duplicate Script"
          >
            <Copy class="w-3.5 h-3.5" />
          </button>

          <button
            @click="requestDeleteScript(script.id)"
            class="p-2 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
            title="Delete Script"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>

          <button
            @click="openEditModal(script)"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-200 text-xs font-bold transition-colors"
          >
            <Edit2 class="w-3.5 h-3.5" />
            Edit
          </button>
        </div>
      </div>
    </div>

    <!-- Script Editor Modal -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md overflow-y-auto"
      @click="closeModal"
    >
      <div
        class="bg-slate-900 border border-white/15 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden my-auto"
        @click.stop
      >
        <!-- Modal Header -->
        <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-slate-900/90">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Code class="w-4 h-4" />
            </div>
            <div>
              <h3 class="text-base font-black text-white">
                {{ isNewScript ? 'Create Event Script' : 'Edit Event Script' }}
              </h3>
              <p class="text-[11px] text-slate-400">
                Safe Python AST code executed within the TaleWeaver turn sandbox.
              </p>
            </div>
          </div>

          <button
            @click="closeModal"
            class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- Modal Body (Scrollable) -->
        <div class="p-6 space-y-5 overflow-y-auto flex-1">
          <!-- Top Row: Name, Script ID, Trigger -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Script Name
              </label>
              <input
                v-model="modalScript.name"
                type="text"
                placeholder="e.g. Trapped Chest Trigger"
                class="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Script ID
              </label>
              <input
                v-model="modalScript.id"
                type="text"
                :disabled="!isNewScript"
                placeholder="e.g. trap_chest_01"
                class="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-emerald-500 disabled:opacity-60 transition-colors"
              />
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Event Trigger
              </label>
              <select
                v-model="modalScript.trigger"
                class="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 transition-colors"
              >
                <option v-for="opt in TRIGGER_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>
          </div>

          <!-- Second Row: Target, Priority, Active Toggle -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
            <div>
              <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Target Entity / Scene <span class="text-slate-500 font-normal">(optional)</span>
              </label>
              <input
                v-model="modalScript.target"
                type="text"
                placeholder="e.g. SCENE_DUNGEON, CHEST_01, *"
                list="target-reference-options"
                class="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-emerald-500 transition-colors"
              />
              <datalist id="target-reference-options">
                <option v-for="ref in referenceOptions || []" :key="ref.id" :value="ref.id">
                  {{ ref.name || ref.id }}
                </option>
              </datalist>
            </div>

            <div>
              <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                Priority <span class="text-slate-500 font-normal">(lower runs first)</span>
              </label>
              <input
                v-model.number="modalScript.priority"
                type="number"
                min="0"
                max="999"
                class="w-full bg-slate-950 border border-white/10 rounded-xl px-3.5 py-2 text-xs font-mono text-white focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>

            <div class="flex items-center gap-3 pb-2">
              <button
                type="button"
                @click="modalScript.is_active = !modalScript.is_active"
                :class="[
                  'w-9 h-5 rounded-full p-0.5 transition-colors',
                  modalScript.is_active ? 'bg-emerald-500' : 'bg-slate-700'
                ]"
              >
                <div
                  :class="[
                    'w-4 h-4 rounded-full bg-white transition-transform',
                    modalScript.is_active ? 'translate-x-4' : 'translate-x-0'
                  ]"
                ></div>
              </button>
              <span class="text-xs font-bold text-slate-300">
                {{ modalScript.is_active ? 'Script Enabled' : 'Script Disabled' }}
              </span>
            </div>
          </div>

          <!-- Code Editor Toolbar -->
          <div class="space-y-2">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Python Script Code
              </label>

              <div class="flex items-center gap-2">
                <!-- Snippet Inserter Dropdown -->
                <select
                  @change="(e: any) => { if (e.target.value) { insertSnippet(e.target.value); e.target.value = ''; } }"
                  class="bg-slate-800 border border-white/10 rounded-lg px-2.5 py-1 text-xs text-slate-300 focus:outline-none focus:border-emerald-500 transition-colors"
                >
                  <option value="">Insert Snippet...</option>
                  <option v-for="snippet in SNIPPET_TEMPLATES" :key="snippet.label" :value="snippet.code">
                    {{ snippet.label }}
                  </option>
                </select>

                <!-- Check Syntax Button -->
                <button
                  type="button"
                  @click="checkSyntax"
                  :disabled="isCheckingSyntax"
                  class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-600/80 hover:bg-emerald-500 text-white text-xs font-bold transition-all disabled:opacity-50"
                >
                  <Play class="w-3 h-3" />
                  {{ isCheckingSyntax ? 'Checking...' : 'Check Syntax' }}
                </button>
              </div>
            </div>

            <!-- Code Textarea -->
            <div class="relative rounded-xl border border-white/10 bg-slate-950 overflow-hidden">
              <textarea
                v-model="modalScript.code"
                rows="12"
                @keydown="handleTabKey"
                placeholder="# Enter Python script here..."
                class="w-full bg-transparent p-4 font-mono text-xs text-emerald-300 focus:outline-none resize-y leading-relaxed"
                spellcheck="false"
              ></textarea>
            </div>
          </div>

          <!-- Syntax Validation Banner -->
          <div
            v-if="syntaxValidationResult"
            :class="[
              'rounded-xl p-4 text-xs border flex items-start gap-3',
              syntaxValidationResult.valid
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
            ]"
          >
            <CheckCircle2 v-if="syntaxValidationResult.valid" class="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <AlertCircle v-else class="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />

            <div class="space-y-1">
              <p class="font-bold">
                {{
                  syntaxValidationResult.valid
                    ? 'Syntax & Security Validation Passed!'
                    : 'Syntax & Security Validation Failed'
                }}
              </p>
              <p v-if="syntaxValidationResult.valid" class="text-slate-300">
                Code conforms to Python grammar and AST security whitelist. Max steps per run: 10,000 instructions.
              </p>
              <ul v-else class="list-disc list-inside space-y-0.5 text-rose-300">
                <li v-for="(err, idx) in syntaxValidationResult.errors" :key="idx">
                  {{ err }}
                </li>
              </ul>
            </div>
          </div>

          <!-- Collapsible API Quick Reference -->
          <div class="border border-white/10 rounded-xl overflow-hidden bg-slate-950/40">
            <button
              type="button"
              @click="showApiReference = !showApiReference"
              class="w-full px-4 py-2.5 flex items-center justify-between text-xs font-bold text-slate-300 hover:bg-white/5 transition-colors"
            >
              <span class="flex items-center gap-2">
                <HelpCircle class="w-4 h-4 text-emerald-400" />
                Scripting Engine API Quick Reference (tw.*)
              </span>
              <ChevronUp v-if="showApiReference" class="w-4 h-4" />
              <ChevronDown v-else class="w-4 h-4" />
            </button>

            <div v-if="showApiReference" class="p-4 border-t border-white/10 text-xs text-slate-300 space-y-3 font-mono">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-white/5">
                  <span class="font-bold text-emerald-400">tw.player</span>
                  <p class="text-[11px] text-slate-400 font-sans mt-0.5">
                    <code>tw.player.hp</code>, <code>tw.player.heal(n)</code>, <code>tw.player.damage(n)</code>, <code>tw.player.has_item(id)</code>
                  </p>
                </div>

                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-white/5">
                  <span class="font-bold text-emerald-400">tw.scene</span>
                  <p class="text-[11px] text-slate-400 font-sans mt-0.5">
                    <code>tw.scene.id</code>, <code>tw.scene.name</code>, <code>tw.scene.description</code>
                  </p>
                </div>

                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-white/5">
                  <span class="font-bold text-emerald-400">tw.exits</span>
                  <p class="text-[11px] text-slate-400 font-sans mt-0.5">
                    <code>tw.exits.lock(id, reason)</code>, <code>tw.exits.unlock(id)</code>, <code>tw.exits.hide(id)</code>, <code>tw.exits.reveal(id)</code>
                  </p>
                </div>

                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-white/5">
                  <span class="font-bold text-emerald-400">tw.npcs</span>
                  <p class="text-[11px] text-slate-400 font-sans mt-0.5">
                    <code>tw.npcs.move(npc_id, target_scene_id)</code>, <code>tw.npcs.get(npc_id)</code>
                  </p>
                </div>

                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-white/5">
                  <span class="font-bold text-emerald-400">tw.vars</span>
                  <p class="text-[11px] text-slate-400 font-sans mt-0.5">
                    <code>tw.vars.get(key, default)</code>, <code>tw.vars.set(key, val)</code>, <code>tw.vars.has(key)</code>
                  </p>
                </div>

                <div class="bg-slate-900/60 p-2.5 rounded-lg border border-white/5">
                  <span class="font-bold text-emerald-400">tw.story & tw.game</span>
                  <p class="text-[11px] text-slate-400 font-sans mt-0.5">
                    <code>tw.story.show_message(text)</code>, <code>tw.game.set_victory(msg)</code>, <code>tw.game.set_game_over(msg)</code>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="px-6 py-4 border-t border-white/10 flex items-center justify-end gap-3 bg-slate-900/90">
          <button
            @click="closeModal"
            class="px-4 py-2 rounded-xl border border-white/10 text-slate-300 font-bold text-xs uppercase tracking-wider hover:bg-white/5 transition-colors"
          >
            Cancel
          </button>
          <button
            @click="saveScript"
            class="px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-black text-xs uppercase tracking-wider shadow-lg shadow-emerald-950/40 transition-all hover:scale-105 active:scale-95"
          >
            {{ isNewScript ? 'Create Script' : 'Save Changes' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div
      v-if="showDeleteConfirmModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md"
      @click="showDeleteConfirmModal = false"
    >
      <div
        class="bg-slate-900 border border-white/15 rounded-2xl p-6 w-full max-w-md shadow-2xl space-y-4"
        @click.stop
      >
        <div class="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
          <Trash2 class="w-5 h-5" />
        </div>
        <div>
          <h3 class="text-base font-bold text-white">Delete Script</h3>
          <p class="text-xs text-slate-400 mt-1">
            Are you sure you want to delete script
            <span class="font-mono text-rose-300">{{ pendingDeleteScriptId }}</span>?
            This action cannot be undone.
          </p>
        </div>
        <div class="flex items-center justify-end gap-3 pt-2">
          <button
            @click="showDeleteConfirmModal = false"
            class="px-4 py-2 rounded-xl border border-white/10 text-slate-300 font-bold text-xs uppercase tracking-wider hover:bg-white/5 transition-colors"
          >
            Cancel
          </button>
          <button
            @click="confirmDeleteScript"
            class="px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-white font-bold text-xs uppercase tracking-wider transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
