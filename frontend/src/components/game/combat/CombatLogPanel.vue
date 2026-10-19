<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { CombatLogEntry } from '@/types'

const props = defineProps<{
  entries: CombatLogEntry[]
  total: number
}>()

const container = ref<HTMLElement | null>(null)

const SOURCE_BY_TYPE: Record<string, { label: string; cls: string }> = {
  player_action: { label: 'You', cls: 'border-emerald-500/50 text-emerald-200' },
  consume: { label: 'You', cls: 'border-emerald-500/50 text-emerald-200' },
  run: { label: 'You', cls: 'border-emerald-500/50 text-emerald-200' },
  enemy_action: { label: 'Enemy', cls: 'border-rose-500/50 text-rose-200' },
  special: { label: 'Event', cls: 'border-violet-400/60 text-violet-200' },
  loot: { label: 'Loot', cls: 'border-amber-400/60 text-amber-200' },
}
const GM_SOURCE = { label: 'GM', cls: 'border-amber-500/30 text-slate-300' }

function source(entry: CombatLogEntry): { label: string; cls: string } {
  return SOURCE_BY_TYPE[entry.type] ?? GM_SOURCE
}

function rollChip(entry: CombatLogEntry): string | null {
  const d = entry.data
  if (!d || d.d20 === undefined || d.total === undefined || d.dc === undefined) return null
  const verdict = d.crit ? 'CRIT' : d.fumble ? 'FUMBLE' : d.success ? 'HIT' : 'MISS'
  return `d20 ${d.d20} → ${d.total} vs ${d.dc} · ${verdict}`
}

function entryKey(entry: CombatLogEntry, idx: number): string {
  return `${entry.timestamp ?? 'ts'}-${idx}`
}

watch(
  () => props.entries.length,
  async () => {
    await nextTick()
    container.value?.scrollTo({ top: container.value.scrollHeight, behavior: 'smooth' })
  },
)
</script>

<template>
  <section class="relative flex flex-col min-h-0 h-full border border-amber-500/20 bg-slate-950/60 rounded-xl backdrop-blur-sm">
    <header class="px-3 py-2 border-b border-amber-500/15 text-[11px] uppercase tracking-[0.22em] font-black flex items-center gap-2 text-amber-300">
      <i class="ra ra-scroll-unfurled text-amber-300/80"></i>
      Battle Chronicle
      <span class="ml-auto text-[10px] text-amber-300/40 font-mono">{{ entries.length }} / {{ total }}</span>
    </header>
    <div ref="container" class="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-3 py-2 space-y-2" aria-live="polite">
      <article
        v-for="(entry, idx) in entries"
        :key="entryKey(entry, idx)"
        class="combat-log-entry border-l-2 pl-2.5 text-[13px] leading-snug"
        :class="source(entry).cls"
      >
        <div class="flex items-center gap-2 mb-0.5">
          <span class="text-[9px] uppercase font-black tracking-[0.14em] opacity-80">{{ source(entry).label }}</span>
          <span v-if="rollChip(entry)" class="font-mono text-[10px] text-cyan-300/90 bg-slate-900/80 px-1.5 rounded border border-cyan-500/20">
            {{ rollChip(entry) }}
          </span>
        </div>
        <p class="text-slate-200/90 break-words">{{ entry.text }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.combat-log-entry {
  animation: combatLogIn 240ms ease-out both;
}

@keyframes combatLogIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(251, 191, 36, 0.25);
  border-radius: 6px;
}
</style>
