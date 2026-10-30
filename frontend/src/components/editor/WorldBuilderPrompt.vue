<script setup lang="ts">
import { toRef } from 'vue'
import { Loader2, Send, Sparkles } from 'lucide-vue-next'
import { WORLD_BUILDER_INSTRUCTION_MAX } from '@/services/worldBuilderService'
import { useWorldBuilderInstructions } from '@/composables/useWorldBuilderInstructions'
import WorldBuilderSuggestionsModal from '@/components/editor/WorldBuilderSuggestionsModal.vue'

const props = defineProps<{
  templateId: string
}>()

const emit = defineEmits<{
  (e: 'notify', message: string, type: 'error' | 'success' | 'info'): void
  (e: 'applied'): void
}>()

const wb = useWorldBuilderInstructions(
  toRef(props, 'templateId'),
  (message, type) => emit('notify', message, type),
  () => emit('applied'),
)
const { instruction, loading, canSubmit } = wb

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || !(event.ctrlKey || event.metaKey)) return
  event.preventDefault()
  void wb.submit()
}
</script>

<template>
  <section class="rounded-2xl border border-violet-500/20 bg-slate-900/60 backdrop-blur-xl p-4 shadow-xl">
    <div class="flex items-center gap-2 mb-3">
      <Sparkles class="w-4 h-4 text-violet-300" />
      <h2 class="text-xs font-black uppercase tracking-[0.2em] text-violet-200">World-Builder</h2>
      <span class="text-[11px] text-slate-500">
        Describe a change, a new NPC/item, or a script/guard &mdash; you will get up to three proposals to choose from.
      </span>
    </div>
    <div class="flex items-end gap-3">
      <div class="flex-1 relative">
        <textarea
          v-model="instruction"
          rows="2"
          :maxlength="WORLD_BUILDER_INSTRUCTION_MAX"
          :disabled="loading"
          placeholder="e.g. &quot;Make the innkeeper more suspicious&quot; or &quot;The chest only opens after the cellar lever was pulled.&quot;"
          class="w-full resize-y rounded-xl bg-slate-950/60 border border-white/10 focus:border-violet-500/50 focus:outline-none px-4 py-3 pr-20 text-sm text-slate-200 placeholder:text-slate-600 disabled:opacity-60"
          @keydown="onKeydown"
        />
        <span class="absolute bottom-2 right-3 text-[10px] font-mono text-slate-600 pointer-events-none">
          {{ instruction.length }} / {{ WORLD_BUILDER_INSTRUCTION_MAX }}
        </span>
      </div>
      <button
        type="button"
        class="shrink-0 h-[52px] px-5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-black uppercase tracking-widest transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed flex items-center gap-2"
        :disabled="!canSubmit"
        title="Send to World-Builder (Ctrl+Enter)"
        @click="wb.submit()"
      >
        <Loader2 v-if="loading" class="w-4 h-4 animate-spin" />
        <Send v-else class="w-4 h-4" />
        <span>Send</span>
      </button>
    </div>

    <WorldBuilderSuggestionsModal
      :open="wb.modalOpen.value"
      :instruction="wb.submittedInstruction.value"
      :proposals="wb.proposals.value"
      :note="wb.note.value"
      :loading="wb.loading.value"
      :applying="wb.applying.value"
      :selected-index="wb.selectedIndex.value"
      :has-backup-confirmed="wb.backupConfirmed.value"
      :error-message="wb.errorMessage.value"
      @close="wb.close()"
      @select="wb.selectedIndex.value = $event"
      @toggle-backup="wb.backupConfirmed.value = $event"
      @retry="wb.retry()"
      @apply="wb.applySelected()"
    />
  </section>
</template>
