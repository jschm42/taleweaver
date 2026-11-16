<script setup lang="ts">
/**
 * PlayAgentPanel — Floating control panel of the Play-Agent, in the adventure's skin.
 *
 * Shown while the agent plays for the player. Lets the player switch between Auto and Step
 * mode, trigger the next step, pause/resume, set the pause between steps, change the
 * personality and dialogue level, give it an instruction for what to do next, and stop it.
 * The minimize button shrinks it to PlayAgentMiniDock.
 * Walkthrough guidance is only selectable once the current chapter's walkthrough is unlocked
 * with XP (always in debug mode); Monkey mode only appears in debug mode.
 */
import { computed, nextTick, ref, watch } from 'vue'
import { ChevronDown, Minus, Pause, Play, StepForward, X } from 'lucide-vue-next'
import {
  PLAY_AGENT_DIALOGUE_LEVELS,
  PLAY_AGENT_PERSONALITIES,
  PLAY_AGENT_STEP_DELAYS,
  usePlayAgent,
  usePlayAgentStatusLabel,
} from '@/composables/usePlayAgent'
import PlayAgentInstruction from './PlayAgentInstruction.vue'

const {
  sheet,
  agentPaused,
  agentLog,
  isStepMode,
  stepDelay,
  waitForTts,
  personality,
  dialogueLevel,
  isBusy,
  canRunStep,
  walkthroughUnlocked,
  debugTools,
  setMinimized,
  setStepMode,
  setPersonality,
  setWalkthroughAllowed,
  setMonkeyMode,
  setStepDelay,
  setWaitForTts,
  setDialogueLevel,
  nextStep,
  togglePause,
  stop,
} = usePlayAgent()

const statusLabel = usePlayAgentStatusLabel()

const heroName = computed(() => sheet.value?.name || 'your hero')
const allowWalkthrough = computed(() => sheet.value?.agent_allow_walkthrough ?? true)
const monkeyMode = computed(() => Boolean(sheet.value?.agent_monkey_mode))

const selectedPersonality = ref(personality.value)
const customText = ref(sheet.value?.agent_custom_personality || '')
const logContainer = ref<HTMLElement | null>(null)

watch(personality, (value) => {
  selectedPersonality.value = value
})

watch(() => sheet.value?.agent_custom_personality, (value) => {
  customText.value = value || ''
})

watch(() => agentLog.value.length, async () => {
  await nextTick()
  logContainer.value?.scrollTo({ top: logContainer.value.scrollHeight, behavior: 'smooth' })
})

// Settings start collapsed so the essentials fit; the choice is remembered per browser.
const SETTINGS_STORAGE_KEY = 'tw.playAgent.settingsOpen'

function readSettingsOpen(): boolean {
  try {
    return window.localStorage.getItem(SETTINGS_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

const settingsOpen = ref(readSettingsOpen())

function toggleSettings(): void {
  settingsOpen.value = !settingsOpen.value
  try {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, settingsOpen.value ? '1' : '0')
  } catch {
    // Blocked storage: the section just starts collapsed next time.
  }
}

const walkthroughTitle = computed(() =>
  walkthroughUnlocked.value
    ? 'Let the agent follow the walkthrough of the current chapter'
    : "Unlock the current chapter's walkthrough under Hints (costs XP) to let the agent use it"
)

const dialogueIndex = computed(() =>
  Math.max(0, PLAY_AGENT_DIALOGUE_LEVELS.findIndex(level => level.id === dialogueLevel.value))
)
const dialogueOption = computed(() => PLAY_AGENT_DIALOGUE_LEVELS[dialogueIndex.value])

async function handleDialogueChange(event: Event): Promise<void> {
  const level = PLAY_AGENT_DIALOGUE_LEVELS[Number((event.target as HTMLInputElement).value)]
  if (level) await setDialogueLevel(level.id)
}

const delayOptions = computed(() => {
  const known = PLAY_AGENT_STEP_DELAYS.some(d => d.seconds === stepDelay.value)
  return known
    ? PLAY_AGENT_STEP_DELAYS
    : [...PLAY_AGENT_STEP_DELAYS, { seconds: stepDelay.value, label: `${stepDelay.value} seconds` }]
})

async function handleDelayChange(event: Event): Promise<void> {
  await setStepDelay(Number((event.target as HTMLSelectElement).value))
}

const customDirty = computed(() =>
  customText.value.trim() !== (sheet.value?.agent_custom_personality || '').trim()
)

async function handlePersonalityChange(): Promise<void> {
  if (selectedPersonality.value === 'custom' && !customText.value.trim()) return
  const text = selectedPersonality.value === 'custom' ? customText.value.trim() : undefined
  await setPersonality(selectedPersonality.value, text)
}

async function applyCustomPersonality(): Promise<void> {
  if (!customText.value.trim()) return
  await setPersonality('custom', customText.value.trim())
}
</script>

<template>
  <aside
    class="tw-agent-panel flex flex-col w-72 max-w-[calc(100vw-2rem)] min-h-0 overflow-hidden"
    aria-label="Play-Agent controls"
  >
    <!-- Header -->
    <header class="flex items-center justify-between gap-2 px-4 py-3 border-b tw-agent-divider">
      <div class="flex items-center gap-2 min-w-0">
        <span :class="['tw-agent-dot', { 'is-busy': isBusy, 'is-paused': !isBusy && agentPaused }]"></span>
        <div class="min-w-0">
          <h2 class="tw-panel-title truncate">Play-Agent</h2>
          <p class="text-[10px] tw-muted truncate">Plays as {{ heroName }}</p>
        </div>
      </div>
      <div class="flex items-center gap-1.5 shrink-0">
        <button
          class="tw-dialog-icon-button w-7 h-7"
          title="Minimize: keep the agent playing with a small control dock"
          aria-label="Minimize Play-Agent panel"
          @click="setMinimized(true)"
        >
          <Minus class="w-3.5 h-3.5" />
        </button>
        <button
          class="tw-dialog-icon-button w-7 h-7"
          title="Stop the Play-Agent and take back control"
          aria-label="Stop Play-Agent"
          @click="stop"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>
    </header>

    <!-- One scrolling body: essentials first, settings collapsible, thoughts last. -->
    <div class="flex-auto min-h-0 overflow-y-auto tw-agent-scroll">
      <div class="flex flex-col gap-3 px-4 py-3">
        <p class="text-[11px] tw-muted truncate" :title="statusLabel" aria-live="polite">{{ statusLabel }}</p>

        <!-- What the agent should do next (same as /instruct in the chat) -->
        <PlayAgentInstruction />

        <!-- Mode and primary action -->
        <div class="flex items-stretch gap-2">
          <div class="tw-agent-segment flex-1" role="group" aria-label="Mode">
            <button :aria-pressed="!isStepMode" @click="setStepMode(false)">Auto</button>
            <button :aria-pressed="isStepMode" @click="setStepMode(true)">Step</button>
          </div>
          <button
            v-if="isStepMode"
            :disabled="!canRunStep"
            class="tw-dialog-button flex-1 !px-2"
            @click="nextStep"
          >
            <StepForward class="w-3.5 h-3.5" />
            {{ isBusy ? 'Running' : 'Next' }}
          </button>
          <button v-else class="tw-dialog-button flex-1 !px-2" @click="togglePause">
            <component :is="agentPaused ? Play : Pause" class="w-3.5 h-3.5" />
            {{ agentPaused ? 'Resume' : 'Pause' }}
          </button>
        </div>

        <!-- Settings (collapsible) -->
        <button
          class="tw-agent-label flex items-center justify-between gap-2 pt-2 border-t tw-agent-divider hover:opacity-80"
          :aria-expanded="settingsOpen"
          @click="toggleSettings"
        >
          <span>Settings</span>
          <ChevronDown :class="['w-3.5 h-3.5 transition-transform', settingsOpen ? 'rotate-180' : '']" />
        </button>

        <div v-if="settingsOpen" class="flex flex-col gap-3">
          <!-- Personality -->
          <label class="flex flex-col gap-1.5">
            <span class="tw-agent-label">Play style</span>
            <select v-model="selectedPersonality" class="tw-agent-field" @change="handlePersonalityChange">
              <option v-for="p in PLAY_AGENT_PERSONALITIES" :key="p.id" :value="p.id">{{ p.label }}</option>
            </select>
          </label>
          <div v-if="selectedPersonality === 'custom'" class="flex flex-col gap-1.5">
            <textarea
              v-model="customText"
              rows="3"
              placeholder="Describe how the agent should play..."
              class="tw-agent-field resize-none"
            ></textarea>
            <button
              :disabled="!customText.trim() || !customDirty"
              class="tw-dialog-button tw-dialog-button--ghost self-end !px-2.5 !py-1 !text-[10px]"
              @click="applyCustomPersonality"
            >
              Apply
            </button>
          </div>

          <!-- Dialogue with characters: taciturn ... full roleplay -->
          <label class="flex flex-col gap-1" :title="dialogueOption.hint">
            <span class="flex items-baseline justify-between gap-2">
              <span class="tw-agent-label">Dialogue</span>
              <span class="text-[11px] font-bold">{{ dialogueOption.label }}</span>
            </span>
            <input
              type="range"
              min="0"
              :max="PLAY_AGENT_DIALOGUE_LEVELS.length - 1"
              step="1"
              :value="dialogueIndex"
              class="tw-agent-range"
              :aria-valuetext="dialogueOption.label"
              @change="handleDialogueChange"
            />
            <span class="flex justify-between text-[9px] tw-muted uppercase tracking-wider">
              <span>Taciturn</span>
              <span>Full roleplay</span>
            </span>
            <span class="text-[10px] tw-muted leading-snug">{{ dialogueOption.hint }}</span>
          </label>

          <!-- Pacing (Auto mode) -->
          <div v-if="!isStepMode" class="flex flex-col gap-1.5">
            <label class="flex flex-col gap-1.5">
              <span class="tw-agent-label">Delay between steps</span>
              <select
                :value="stepDelay"
                class="tw-agent-field"
                title="Extra pause before the agent plays its next step"
                @change="handleDelayChange"
              >
                <option v-for="d in delayOptions" :key="d.seconds" :value="d.seconds">{{ d.label }}</option>
              </select>
            </label>
            <label
              class="tw-agent-check"
              title="Only continue once text-to-speech has finished reading the narration (needs auto-speech)"
            >
              <input type="checkbox" :checked="waitForTts" @change="setWaitForTts(!waitForTts)" />
              Wait for speech to finish
            </label>
          </div>

          <!-- Options -->
          <div class="flex flex-col gap-1.5">
            <label :class="['tw-agent-check', { 'is-disabled': !walkthroughUnlocked }]" :title="walkthroughTitle">
              <input
                type="checkbox"
                :checked="allowWalkthrough && walkthroughUnlocked"
                :disabled="!walkthroughUnlocked"
                @change="setWalkthroughAllowed(!allowWalkthrough)"
              />
              Use walkthrough
            </label>
            <p v-if="!walkthroughUnlocked" class="text-[10px] tw-muted leading-snug pl-6">
              Unlock this chapter's walkthrough under Hints first (costs XP).
            </p>
            <label
              v-if="debugTools"
              class="tw-agent-check"
              title="Debug: deliberately try invalid or chaotic actions to stress-test the engine"
            >
              <input type="checkbox" :checked="monkeyMode" @change="setMonkeyMode(!monkeyMode)" />
              Monkey mode (debug)
            </label>
          </div>
        </div>
      </div>

      <!-- Inner voice / decision log (own height limit, newest at the bottom) -->
      <div class="flex flex-col gap-2 px-4 py-3 border-t tw-agent-divider">
        <span class="tw-agent-label">{{ heroName }}'s thoughts</span>
        <div ref="logContainer" class="flex flex-col gap-3 max-h-48 overflow-y-auto tw-agent-scroll pr-1">
          <p v-if="agentLog.length === 0" class="text-[11px] tw-muted italic">No decisions yet.</p>
          <div v-for="(entry, idx) in agentLog" :key="idx" class="flex flex-col gap-1 text-[11px]">
            <span class="text-[9px] font-mono tw-muted">{{ entry.timestamp }}</span>
            <p class="tw-agent-thought">{{ entry.thought }}</p>
            <p v-if="entry.action" class="tw-agent-action">&gt; {{ entry.action }}</p>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
