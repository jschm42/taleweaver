<script setup lang="ts">
/**
 * PlayAgentMiniDock — The minimized Play-Agent panel, a small floating card at the bottom right.
 *
 * Keeps the story in view while the agent plays: status light and line, the hero's latest
 * thought, an instruction field, play style and dialogue level, and the essential controls (Pause/Resume or Next
 * Step, Auto/Step, expand, stop). Choosing the Custom play style without a description opens
 * the full panel.
 */
import { computed } from 'vue'
import { Maximize2, Pause, Play, Square, StepForward } from 'lucide-vue-next'
import {
  PLAY_AGENT_DIALOGUE_LEVELS,
  PLAY_AGENT_PERSONALITIES,
  usePlayAgent,
  usePlayAgentStatusLabel,
} from '@/composables/usePlayAgent'
import PlayAgentInstruction from './PlayAgentInstruction.vue'

const {
  personality,
  dialogueLevel,
  changePlayStyle,
  setDialogueLevel,
  agentPaused,
  isStepMode,
  isBusy,
  canRunStep,
  lastEntry,
  setMinimized,
  setStepMode,
  nextStep,
  togglePause,
  stop,
} = usePlayAgent()

const statusLabel = usePlayAgentStatusLabel()

const primaryLabel = computed(() => {
  if (isStepMode.value) return 'Next step'
  return agentPaused.value ? 'Resume' : 'Pause'
})

const primaryIcon = computed(() => {
  if (isStepMode.value) return StepForward
  return agentPaused.value ? Play : Pause
})

function handlePrimary(): void {
  if (isStepMode.value) {
    void nextStep()
    return
  }
  togglePause()
}
</script>

<template>
  <div
    class="tw-agent-panel flex flex-col gap-2 w-64 max-w-[calc(100vw-2rem)] px-3 py-2.5"
    role="region"
    aria-label="Play-Agent (minimized)"
  >
    <div class="flex items-center gap-2 min-w-0">
      <span :class="['tw-agent-dot', { 'is-busy': isBusy, 'is-paused': !isBusy && agentPaused }]"></span>
      <span class="tw-panel-title shrink-0">Play-Agent</span>
      <span class="text-[10px] tw-muted truncate" :title="statusLabel" aria-live="polite">{{ statusLabel }}</span>
    </div>

    <p
      v-if="lastEntry"
      class="tw-agent-thought text-[11px] line-clamp-2"
      :title="lastEntry.action ? `${lastEntry.thought}\n> ${lastEntry.action}` : lastEntry.thought"
    >
      {{ lastEntry.thought }}
    </p>

    <PlayAgentInstruction compact />

    <div class="grid grid-cols-2 gap-1.5">
      <label class="flex flex-col gap-0.5 min-w-0">
        <span class="tw-agent-label">Play style</span>
        <select
          :value="personality"
          class="tw-agent-field tw-agent-field--compact"
          title="How the agent plays"
          @change="changePlayStyle(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="p in PLAY_AGENT_PERSONALITIES" :key="p.id" :value="p.id">{{ p.label }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-0.5 min-w-0">
        <span class="tw-agent-label">Dialogue</span>
        <select
          :value="dialogueLevel"
          class="tw-agent-field tw-agent-field--compact"
          title="How much the agent talks with characters"
          @change="setDialogueLevel(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="d in PLAY_AGENT_DIALOGUE_LEVELS" :key="d.id" :value="d.id" :title="d.hint">
            {{ d.label }}
          </option>
        </select>
      </label>
    </div>

    <div class="flex items-center gap-1.5">
      <button
        class="tw-dialog-button flex-1 !px-2 !py-1.5"
        :disabled="isStepMode && !canRunStep"
        :title="primaryLabel"
        @click="handlePrimary"
      >
        <component :is="primaryIcon" class="w-3.5 h-3.5" />
        {{ primaryLabel }}
      </button>
      <button
        class="tw-dialog-button tw-dialog-button--ghost !px-2 !py-1.5"
        :title="isStepMode ? 'Switch to Auto mode' : 'Switch to Step mode'"
        @click="setStepMode(!isStepMode)"
      >
        {{ isStepMode ? 'Auto' : 'Step' }}
      </button>
      <button
        class="tw-dialog-icon-button w-7 h-7 shrink-0"
        title="Open the full Play-Agent panel"
        aria-label="Expand Play-Agent panel"
        @click="setMinimized(false)"
      >
        <Maximize2 class="w-3.5 h-3.5" />
      </button>
      <button
        class="tw-dialog-icon-button w-7 h-7 shrink-0"
        title="Stop the Play-Agent and take back control"
        aria-label="Stop Play-Agent"
        @click="stop"
      >
        <Square class="w-3 h-3" />
      </button>
    </div>
  </div>
</template>
