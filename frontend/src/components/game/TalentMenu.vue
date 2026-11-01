<script setup lang="ts">
/**
 * TalentMenu — action-bar button that lists the protagonist's unlocked talents.
 *
 * Picking a talent sends "/talent <ID>" (or "/talent <ID> | <TARGET>" after choosing a target
 * among the NPCs and items in the scene and the inventory). Hidden while the hero has no talents.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ChevronLeft, Sparkles, X } from 'lucide-vue-next'
import {
  sheetTalents,
  talentAcceptsEntity,
  talentCommand,
  talentCostLabel,
  talentNeedsTarget,
  talentUsesLeft,
  type NormalizedTalent,
} from '@/utils/talents'

type TargetOption = { id: string; name: string; kind: 'NPC' | 'OBJECT'; where: string }

const props = defineProps<{
  sheet?: any
  entities?: any[]
  disabled?: boolean
}>()

const emit = defineEmits<{ use: [command: string] }>()

const open = ref(false)
const picking = ref<NormalizedTalent | null>(null)
const rootEl = ref<HTMLElement | null>(null)

const talents = computed(() => sheetTalents(props.sheet))

function pool(talent: NormalizedTalent): number {
  return Number(props.sheet?.[talent.cost_type]) || 0
}

function blockedReason(talent: NormalizedTalent): string | null {
  if (talentUsesLeft(talent, props.sheet?.talent_uses) === 0) return 'Used up for this adventure'
  if (pool(talent) < talent.cost) return `Needs ${talentCostLabel(talent)}`
  return null
}

function usesLabel(talent: NormalizedTalent): string {
  const left = talentUsesLeft(talent, props.sheet?.talent_uses)
  return left === null ? '' : `${left}/${talent.max_uses} left`
}

const targetOptions = computed<TargetOption[]>(() => {
  const talent = picking.value
  if (!talent) return []
  const scene = (props.entities ?? [])
    .filter((e: any) => e?.id && !e.is_hidden && talentAcceptsEntity(talent, e.entity_type))
    .map((e: any) => ({ id: String(e.id), name: String(e.name || e.id), kind: e.entity_type, where: 'here' }))
  const carried = talentAcceptsEntity(talent, 'OBJECT')
    ? (props.sheet?.inventory ?? [])
        .filter((i: any) => i && typeof i === 'object' && i.id)
        .map((i: any) => ({ id: String(i.id), name: String(i.name || i.id), kind: 'OBJECT' as const, where: 'carried' }))
    : []
  const seen = new Set<string>()
  return [...scene, ...carried].filter((t) => !seen.has(t.id) && !!seen.add(t.id))
})

function close(): void {
  open.value = false
  picking.value = null
}

function choose(talent: NormalizedTalent): void {
  if (blockedReason(talent) || props.disabled) return
  if (talent.target_type === 'NONE') {
    emit('use', talentCommand(talent.id))
    close()
    return
  }
  picking.value = talent
}

function useOn(targetId: string | null): void {
  if (!picking.value) return
  emit('use', talentCommand(picking.value.id, targetId))
  close()
}

function onDocumentPointer(event: MouseEvent): void {
  if (rootEl.value && !rootEl.value.contains(event.target as Node)) close()
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') close()
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('mousedown', onDocumentPointer)
    document.addEventListener('keydown', onKey)
    return
  }
  document.removeEventListener('mousedown', onDocumentPointer)
  document.removeEventListener('keydown', onKey)
})

watch(() => props.disabled, (disabled) => {
  if (disabled) close()
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentPointer)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div v-if="talents.length" ref="rootEl" class="relative shrink-0">
    <button
      type="button"
      :disabled="disabled"
      aria-label="Talents"
      title="Talents"
      class="talent-trigger flex items-center justify-center w-9 h-9 rounded-lg border border-violet-500/30 bg-violet-950/30 text-violet-300 transition-all active:scale-95"
      :class="[disabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-violet-900/40 hover:text-violet-100 cursor-pointer', open ? 'ring-1 ring-violet-400/60' : '']"
      @click="open ? close() : (open = true)"
    >
      <Sparkles class="w-4 h-4" />
    </button>

    <div
      v-if="open"
      class="absolute bottom-full left-0 mb-2 w-80 max-h-96 overflow-hidden bg-slate-900/95 backdrop-blur-xl border border-violet-500/30 rounded-2xl shadow-2xl z-[150] flex flex-col"
      role="menu"
    >
      <div class="px-3 py-2 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <button v-if="picking" type="button" class="flex items-center gap-1 text-[10px] font-black uppercase tracking-[0.2em] text-violet-300" @click="picking = null">
          <ChevronLeft class="w-3.5 h-3.5" /> {{ picking.name }} on…
        </button>
        <span v-else class="text-[10px] font-black uppercase tracking-[0.2em] text-violet-300">Talents</span>
        <button type="button" class="p-1 text-slate-500 hover:text-white" aria-label="Close" @click="close"><X class="w-3.5 h-3.5" /></button>
      </div>

      <div v-if="!picking" class="overflow-y-auto p-1">
        <button
          v-for="t in talents"
          :key="t.id"
          type="button"
          role="menuitem"
          class="w-full text-left p-2.5 rounded-xl transition-colors flex flex-col gap-0.5"
          :class="blockedReason(t) ? 'opacity-50 cursor-not-allowed' : 'hover:bg-violet-500/15 cursor-pointer'"
          :title="blockedReason(t) || t.description"
          @click="choose(t)"
        >
          <span class="flex items-center justify-between gap-2">
            <span class="text-sm font-bold text-white truncate">{{ t.name }}</span>
            <span class="text-[10px] font-mono text-violet-300 shrink-0">{{ talentCostLabel(t) }}</span>
          </span>
          <span class="text-[11px] text-slate-400 line-clamp-2">{{ t.description }}</span>
          <span class="text-[10px] text-slate-500">
            {{ blockedReason(t) || usesLabel(t) }}
          </span>
        </button>
        <p class="px-2.5 py-2 text-[10px] text-slate-500">Tip: you can also type "use &lt;talent&gt;" or "cast &lt;talent&gt; on &lt;target&gt;".</p>
      </div>

      <div v-else class="overflow-y-auto p-1">
        <button
          v-if="!talentNeedsTarget(picking)"
          type="button"
          class="w-full text-left px-3 py-2 rounded-xl text-sm font-bold text-slate-200 hover:bg-violet-500/15"
          @click="useOn(null)"
        >No target</button>
        <button
          v-for="target in targetOptions"
          :key="target.id"
          type="button"
          class="w-full text-left px-3 py-2 rounded-xl hover:bg-violet-500/15 flex items-center justify-between gap-2"
          @click="useOn(target.id)"
        >
          <span class="text-sm font-bold text-slate-100 truncate">{{ target.name }}</span>
          <span class="text-[10px] uppercase tracking-widest text-slate-500 shrink-0">{{ target.kind === 'NPC' ? 'character' : target.where }}</span>
        </button>
        <p v-if="!targetOptions.length" class="px-3 py-3 text-xs text-slate-500 italic">Nothing here to use {{ picking.name }} on.</p>
      </div>
    </div>
  </div>
</template>
