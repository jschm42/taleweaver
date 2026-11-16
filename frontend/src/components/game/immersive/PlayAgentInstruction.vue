<script setup lang="ts">
/**
 * PlayAgentInstruction — Tell the Play-Agent what to do next.
 *
 * Shows the current instruction (with a clear button) or a queued one, and a field to send a
 * new instruction. Enter sends, Shift+Enter adds a line (full panel). `compact` is the
 * single-line variant of the minimized dock. Same effect as `/instruct <text>` in the chat.
 */
import { ref } from 'vue'
import { Send, X } from 'lucide-vue-next'
import { usePlayAgent } from '@/composables/usePlayAgent'

const props = defineProps<{
  compact?: boolean
}>()

const { instruction, pendingInstruction, sendInstruction } = usePlayAgent()

const draft = ref('')

async function submit(): Promise<void> {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  await sendInstruction(text)
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey) return
  event.preventDefault()
  void submit()
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <span v-if="!props.compact" class="tw-agent-label">Your instruction</span>

    <div
      v-if="instruction && pendingInstruction === null"
      class="flex items-start gap-1.5 tw-card px-2 py-1.5 text-[11px]"
    >
      <p :class="['flex-1 min-w-0 leading-snug', props.compact ? 'truncate' : '']" :title="instruction">
        {{ instruction }}
      </p>
      <button
        class="tw-dialog-icon-button w-5 h-5 shrink-0"
        title="Clear the instruction: the agent decides on its own again"
        aria-label="Clear instruction"
        @click="sendInstruction('')"
      >
        <X class="w-3 h-3" />
      </button>
    </div>
    <p v-else-if="pendingInstruction !== null" class="text-[10px] tw-muted leading-snug truncate">
      {{ pendingInstruction ? `Queued for the next step: ${pendingInstruction}` : 'Clearing after this step...' }}
    </p>

    <div class="flex items-end gap-1.5">
      <input
        v-if="props.compact"
        v-model="draft"
        type="text"
        maxlength="500"
        placeholder="Tell the agent what to do..."
        class="tw-agent-field tw-agent-field--compact flex-1 min-w-0"
        aria-label="Instruction for the Play-Agent"
        @keydown="handleKeydown"
      />
      <textarea
        v-else
        v-model="draft"
        rows="2"
        maxlength="500"
        placeholder="e.g. Ask the innkeeper about the missing girl"
        class="tw-agent-field resize-none flex-1 min-w-0"
        aria-label="Instruction for the Play-Agent"
        @keydown="handleKeydown"
      ></textarea>
      <button
        class="tw-dialog-icon-button w-7 h-7 shrink-0"
        :disabled="!draft.trim()"
        title="Send the instruction (Enter)"
        aria-label="Send instruction"
        @click="submit"
      >
        <Send class="w-3.5 h-3.5" />
      </button>
    </div>
  </div>
</template>
