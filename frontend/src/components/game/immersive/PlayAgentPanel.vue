<script setup lang="ts">
/**
 * PlayAgentPanel — Right-side control panel for the autonomous Play-Agent.
 *
 * Shown while the agent is active. Lets the player switch between Auto and Step mode,
 * trigger the next step, pause/resume, set the pause between steps (fixed delay and/or
 * waiting for text-to-speech), change the personality and stop the agent.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { PLAY_AGENT_PERSONALITIES, PLAY_AGENT_STEP_DELAYS, usePlayAgent } from '@/composables/usePlayAgent'

const {
  sheet,
  agentPaused,
  agentLog,
  statusText,
  isStepMode,
  stepDelay,
  waitForTts,
  autoLoopPhase,
  nextStepAt,
  isBusy,
  canRunStep,
  setStepMode,
  setPersonality,
  setWalkthroughAllowed,
  setMonkeyMode,
  setStepDelay,
  setWaitForTts,
  nextStep,
  togglePause,
  stop,
} = usePlayAgent()

const personality = computed(() => sheet.value?.agent_personality || 'casual')
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

// Ticks once per second while a countdown to the next step is shown.
const now = ref(Date.now())
const clockTimer = window.setInterval(() => {
  now.value = Date.now()
}, 1000)
onUnmounted(() => window.clearInterval(clockTimer))

const secondsToNextStep = computed(() =>
  nextStepAt.value ? Math.max(0, Math.ceil((nextStepAt.value - now.value) / 1000)) : 0
)

const statusLabel = computed(() => {
  if (isBusy.value) return statusText.value || 'Agent is thinking...'
  if (isStepMode.value) return 'Waiting for next step'
  if (agentPaused.value) return 'Paused - press Resume to continue'
  if (autoLoopPhase.value === 'speech') return 'Waiting for the narration to finish...'
  if (autoLoopPhase.value === 'delay' && secondsToNextStep.value > 1) {
    return `Next step in ${secondsToNextStep.value} s`
  }
  return 'Playing autonomously'
})

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
    class="flex flex-col shrink-0 w-64 lg:w-72 max-h-full min-h-0 bg-slate-950/90 backdrop-blur-xl border border-indigo-500/30 rounded-2xl shadow-[0_0_25px_rgba(99,102,241,0.15)] text-slate-200 overflow-hidden"
    aria-label="Play-Agent controls"
  >
    <!-- Header -->
    <header class="flex items-center justify-between gap-2 px-4 py-3 border-b border-slate-800/80">
      <div class="flex items-center gap-2 min-w-0">
        <span
          :class="[
            'w-2.5 h-2.5 rounded-full shrink-0',
            isBusy ? 'bg-indigo-400 animate-ping' : agentPaused ? 'bg-amber-400' : 'bg-emerald-400'
          ]"
        ></span>
        <h2 class="text-xs font-black uppercase tracking-[0.2em] text-indigo-200">Play-Agent</h2>
      </div>
      <button
        class="px-2.5 py-1 bg-red-600/80 hover:bg-red-600 border border-red-500/50 text-white rounded-lg text-[10px] font-black uppercase tracking-wider transition-all active:scale-95"
        title="Stop the Play-Agent and take back control"
        @click="stop"
      >
        Stop
      </button>
    </header>

    <div class="flex flex-col gap-4 px-4 py-3 border-b border-slate-800/80">
      <p class="text-[11px] text-slate-400 truncate" :title="statusLabel">{{ statusLabel }}</p>

      <!-- Mode -->
      <div class="flex flex-col gap-1.5">
        <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500">Mode</span>
        <div class="grid grid-cols-2 gap-1 p-1 bg-slate-900 rounded-lg border border-slate-800">
          <button
            :class="[
              'py-1.5 rounded-md text-[11px] font-bold uppercase tracking-wider transition-colors',
              !isStepMode ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
            ]"
            @click="setStepMode(false)"
          >
            Auto
          </button>
          <button
            :class="[
              'py-1.5 rounded-md text-[11px] font-bold uppercase tracking-wider transition-colors',
              isStepMode ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
            ]"
            @click="setStepMode(true)"
          >
            Step
          </button>
        </div>
      </div>

      <!-- Primary action -->
      <button
        v-if="isStepMode"
        :disabled="!canRunStep"
        class="w-full py-2 bg-emerald-600/80 hover:bg-emerald-600 border border-emerald-500/50 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-[11px] font-black uppercase tracking-[0.15em] transition-all active:scale-95"
        @click="nextStep"
      >
        {{ isBusy ? 'Running...' : 'Next Step' }}
      </button>
      <button
        v-else
        class="w-full py-2 bg-indigo-600/80 hover:bg-indigo-600 border border-indigo-500/50 text-white rounded-lg text-[11px] font-black uppercase tracking-[0.15em] transition-all active:scale-95"
        @click="togglePause"
      >
        {{ agentPaused ? 'Resume' : 'Pause' }}
      </button>

      <!-- Pacing (Auto mode) -->
      <div v-if="!isStepMode" class="flex flex-col gap-1.5">
        <label class="flex flex-col gap-1.5">
          <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500">Delay between steps</span>
          <select
            :value="stepDelay"
            class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500/60"
            title="Extra pause before the agent plays its next step"
            @change="handleDelayChange"
          >
            <option v-for="d in delayOptions" :key="d.seconds" :value="d.seconds">{{ d.label }}</option>
          </select>
        </label>
        <label
          class="flex items-center gap-2 cursor-pointer select-none text-[11px]"
          title="Only continue once text-to-speech has finished reading the narration (needs auto-speech)"
        >
          <input
            type="checkbox"
            :checked="waitForTts"
            class="w-3.5 h-3.5 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500/50 focus:ring-offset-slate-950 focus:ring-1"
            @change="setWaitForTts(!waitForTts)"
          />
          Wait for speech to finish
        </label>
      </div>

      <!-- Personality -->
      <label class="flex flex-col gap-1.5">
        <span class="text-[10px] font-bold uppercase tracking-wider text-slate-500">Personality</span>
        <select
          v-model="selectedPersonality"
          class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500/60"
          @change="handlePersonalityChange"
        >
          <option v-for="p in PLAY_AGENT_PERSONALITIES" :key="p.id" :value="p.id">{{ p.label }}</option>
        </select>
      </label>
      <div v-if="selectedPersonality === 'custom'" class="flex flex-col gap-1.5">
        <textarea
          v-model="customText"
          rows="3"
          placeholder="Describe how the agent should play..."
          class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500/60"
        ></textarea>
        <button
          :disabled="!customText.trim() || !customDirty"
          class="self-end px-2.5 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-700 rounded-md text-[10px] font-bold uppercase tracking-wider"
          @click="applyCustomPersonality"
        >
          Apply
        </button>
      </div>

      <!-- Options -->
      <div class="flex flex-col gap-1.5 text-[11px]">
        <label class="flex items-center gap-2 cursor-pointer select-none" title="Allow the agent to consult the sequence walkthrough">
          <input
            type="checkbox"
            :checked="allowWalkthrough"
            class="w-3.5 h-3.5 rounded border-slate-700 bg-slate-900 text-cyan-600 focus:ring-cyan-500/50 focus:ring-offset-slate-950 focus:ring-1"
            @change="setWalkthroughAllowed(!allowWalkthrough)"
          />
          Use walkthrough
        </label>
        <label class="flex items-center gap-2 cursor-pointer select-none" title="Deliberately try invalid or chaotic actions to stress-test the engine">
          <input
            type="checkbox"
            :checked="monkeyMode"
            class="w-3.5 h-3.5 rounded border-slate-700 bg-slate-900 text-amber-600 focus:ring-amber-500/50 focus:ring-offset-slate-950 focus:ring-1"
            @change="setMonkeyMode(!monkeyMode)"
          />
          Monkey mode
        </label>
      </div>
    </div>

    <!-- Decision log -->
    <div ref="logContainer" class="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-4 py-3 flex flex-col gap-3">
      <p v-if="agentLog.length === 0" class="text-[11px] text-slate-500 italic">No decisions yet.</p>
      <div v-for="(entry, idx) in agentLog" :key="idx" class="flex flex-col gap-1 text-[11px]">
        <span class="text-[9px] font-mono text-slate-600">{{ entry.timestamp }}</span>
        <p class="text-indigo-200/90 italic leading-snug">{{ entry.thought }}</p>
        <p v-if="entry.action" class="font-mono text-emerald-300">&gt; {{ entry.action }}</p>
      </div>
    </div>
  </aside>
</template>
