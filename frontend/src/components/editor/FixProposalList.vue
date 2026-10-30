<script setup lang="ts">
import { ArrowRight } from 'lucide-vue-next'
import type { FixProposal } from '@/services/adventureService'

const props = defineProps<{
  proposals: FixProposal[]
  selectedIndex: number
  radioName: string
}>()

const emit = defineEmits<{
  (e: 'select', index: number): void
}>()

// Create patches read as an action, e.g. 'new NPC “OLD_FISHERMAN”'.
const TARGET_LABELS: Record<string, string> = { new_npc: 'new NPC', new_object: 'new object' }

function describeTarget(targetType: string, targetId?: string | null): string {
  const label = TARGET_LABELS[targetType] || targetType
  const id = (targetId ?? '').trim()
  if (!id) return label
  return `${label} “${id}”`
}
</script>

<template>
  <div class="space-y-3">
    <div
      v-for="(proposal, idx) in props.proposals"
      :key="`${proposal.title}-${idx}`"
      class="rounded-2xl border transition-all p-4 space-y-3"
      :class="
        props.selectedIndex === idx
          ? 'border-violet-400/60 bg-violet-500/10 shadow-lg shadow-violet-900/30'
          : 'border-white/10 bg-white/5 hover:border-white/20'
      "
    >
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          type="radio"
          :name="props.radioName"
          class="mt-1 accent-violet-500 cursor-pointer"
          :checked="props.selectedIndex === idx"
          @change="emit('select', idx)"
        />
        <div class="flex-1 min-w-0 space-y-2">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-widest bg-violet-500/15 border border-violet-500/30 text-violet-200">
              Option {{ idx + 1 }}
            </span>
            <h4 class="text-sm font-black text-white">{{ proposal.title }}</h4>
          </div>
          <p class="text-xs text-slate-300 leading-relaxed">{{ proposal.summary }}</p>
          <p
            v-if="proposal.rationale"
            class="text-[11px] text-slate-400 italic leading-relaxed"
          >
            Rationale: {{ proposal.rationale }}
          </p>
          <div class="rounded-lg border border-white/10 bg-slate-950/60 p-3 space-y-2">
            <p class="text-[10px] uppercase tracking-widest text-slate-500 font-black">
              What will change
            </p>
            <ul class="space-y-1.5">
              <li
                v-for="(patch, pIdx) in proposal.patches"
                :key="`${patch.target_type}-${patch.target_id || ''}-${pIdx}`"
                class="flex items-start gap-2 text-[11px] text-slate-300"
              >
                <ArrowRight class="w-3 h-3 text-violet-300 mt-0.5 shrink-0" />
                <span class="leading-relaxed">
                  <span class="font-bold text-violet-200">{{ describeTarget(patch.target_type, patch.target_id) }}</span>
                  <span v-if="patch.description"> &mdash; {{ patch.description }}</span>
                </span>
              </li>
            </ul>
          </div>
        </div>
      </label>
    </div>
  </div>
</template>
