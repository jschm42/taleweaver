<script setup lang="ts">
/**
 * DebugNpcDetailDialog — everything the debug inspector knows about one NPC: vitals and stats,
 * persona and GM notes, movement, inventory, NPC memory and conversations, plus the debug
 * actions (heal, kill, unhide). Esc or a click outside closes it.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Compass, Heart, Package, Sparkles, Users, X } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'
import DebugDownloadButton from './DebugDownloadButton.vue'
import DebugNpcSocialPanel from './DebugNpcSocialPanel.vue'

const props = defineProps<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  npc: any
  gameId?: string
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  command: [cmd: string]
}>()

const dialogRef = ref<HTMLElement | null>(null)
const hpPercent = computed(() => Math.min(100, Math.max(0, (props.npc.hp / (props.npc.max_hp || 100)) * 100)))
const hpClass = computed(() => (hpPercent.value > 50 ? 'bg-emerald-500' : hpPercent.value > 20 ? 'bg-amber-500' : 'bg-red-500'))
const STAT_LABELS: [string, string][] = [
  ['strength', 'STR'],
  ['dexterity', 'DEX'],
  ['intelligence', 'INT'],
  ['wisdom', 'WIS'],
  ['charisma', 'CHA'],
  ['armor_class', 'AC'],
]

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return
  // The inspector closes on Esc too: only this dialog may close.
  event.stopImmediatePropagation()
  emit('close')
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown, true)
  nextTick(() => dialogRef.value?.focus())
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown, true))
</script>

<template>
  <div class="fixed inset-0 z-[130] flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm" @click.self="emit('close')">
    <div
      ref="dialogRef"
      role="dialog"
      aria-modal="true"
      :aria-label="`NPC ${npc.name}`"
      tabindex="-1"
      class="w-full max-w-3xl max-h-[88vh] flex flex-col bg-slate-900 border border-cyan-500/40 rounded-2xl shadow-2xl overflow-hidden text-slate-200 focus:outline-none"
    >
      <!-- Header -->
      <div class="flex items-start gap-4 px-5 py-4 bg-slate-950/90 border-b border-slate-800 shrink-0">
        <div class="w-16 h-16 rounded-xl overflow-hidden bg-slate-950 border border-slate-700/80 shrink-0">
          <img v-if="npc.image_url" :src="getImageUrl(npc.image_url)" class="w-full h-full object-cover" :alt="npc.name" />
          <div v-else class="w-full h-full flex items-center justify-center text-slate-600"><Users class="w-6 h-6" /></div>
        </div>
        <div class="flex-1 min-w-0 space-y-1">
          <div class="flex items-center gap-2 flex-wrap">
            <h3 class="text-base font-black text-white truncate">{{ npc.name }}</h3>
            <span
              class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider"
              :class="npc.is_alive ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-red-500/20 text-red-300 border border-red-500/40'"
            >
              {{ npc.is_alive ? 'Alive' : 'Defeated' }}
            </span>
            <span v-if="npc.is_hidden" class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-amber-500/20 text-amber-300 border border-amber-500/40">Hidden</span>
            <span v-if="npc.is_hostile" class="px-2 py-0.5 rounded-full text-[10px] font-black uppercase bg-red-500/20 text-red-300 border border-red-500/40">Hostile</span>
          </div>
          <div class="flex items-center gap-1.5 text-xs font-mono text-slate-400">
            <span>{{ npc.id }}</span>
            <span v-if="npc.role" class="text-slate-500">· {{ npc.role }}</span>
            <DebugDownloadButton v-if="gameId" :game-id="gameId" :entity-id="npc.id" compact />
          </div>
          <div class="flex items-center gap-1 text-xs text-slate-300">
            <Compass class="w-3 h-3 text-cyan-400" />
            {{ npc.current_scene_name || npc.current_scene_id }}
            <span v-if="npc.is_in_current_scene" class="text-cyan-300">(here)</span>
          </div>
        </div>
        <button
          type="button"
          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          aria-label="Close NPC details"
          @click="emit('close')"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto custom-scrollbar p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="space-y-4">
          <!-- Vitals & stats -->
          <div class="space-y-2 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
            <div class="flex items-center justify-between text-[11px] font-mono">
              <span class="flex items-center gap-1 text-red-400 font-bold"><Heart class="w-3 h-3 fill-red-400" /> HP</span>
              <span class="text-slate-300 font-bold">{{ npc.hp }} / {{ npc.max_hp }}</span>
            </div>
            <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
              <div class="h-full" :class="hpClass" :style="{ width: `${hpPercent}%` }"></div>
            </div>
            <div class="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400">
              <span>STA: {{ npc.stamina }} / {{ npc.max_stamina }}</span>
              <span class="text-right">MANA: {{ npc.mana }} / {{ npc.max_mana }}</span>
            </div>
            <div v-if="npc.stats" class="grid grid-cols-3 gap-1 text-[10px] font-mono text-slate-400 pt-1 border-t border-slate-800/60">
              <div v-for="[key, label] in STAT_LABELS" :key="key">
                {{ label }}: <strong class="text-slate-200">{{ npc.stats[key] }}</strong>
              </div>
            </div>
          </div>

          <!-- Persona -->
          <div v-if="npc.character || npc.goal || npc.description" class="bg-violet-950/30 border border-violet-500/30 rounded-xl p-3 space-y-1 text-[11px] font-mono leading-snug break-words">
            <div class="text-[9px] font-black uppercase tracking-wider text-violet-400">Persona</div>
            <p v-if="npc.character" class="text-violet-200/90"><span class="text-violet-400 font-bold">Character:</span> {{ npc.character }}</p>
            <p v-if="npc.goal" class="text-violet-200/90"><span class="text-violet-400 font-bold">Goal:</span> {{ npc.goal }}</p>
            <p v-if="npc.description" class="text-violet-200/70"><span class="text-violet-400 font-bold">Description:</span> {{ npc.description }}</p>
          </div>

          <!-- GM notes -->
          <div v-if="npc.notes" class="bg-amber-950/30 border border-amber-500/30 rounded-xl p-3 space-y-1">
            <div class="flex items-center gap-1 text-[9px] font-black uppercase tracking-wider text-amber-400"><Sparkles class="w-3 h-3" /> GM Status & Notes</div>
            <p class="text-[11px] text-amber-200/90 font-mono italic leading-snug break-words">"{{ npc.notes }}"</p>
          </div>

          <!-- Movement -->
          <div class="text-[11px] font-mono text-slate-400 space-y-0.5 px-1">
            <div>
              <span class="text-slate-500 font-bold uppercase">Movement:</span>
              {{ npc.moveable ? 'Movable' : 'Stationary' }}
            </div>
            <div v-if="npc.moveable && npc.allowed_scenes?.length">
              <span class="text-slate-500 font-bold uppercase">Allowed scenes:</span> {{ npc.allowed_scenes.join(', ') }}
            </div>
            <div v-if="npc.start_scene_id"><span class="text-slate-500 font-bold uppercase">Start scene:</span> {{ npc.start_scene_id }}</div>
          </div>

          <!-- Inventory -->
          <div v-if="npc.inventory?.length" class="space-y-1">
            <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
              <Package class="w-3 h-3 text-cyan-400" /> Carrying ({{ npc.inventory.length }})
            </div>
            <div class="flex flex-wrap gap-1">
              <span
                v-for="(itm, idx) in npc.inventory"
                :key="idx"
                class="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-300"
              >
                {{ itm.name || itm.id || itm }}
              </span>
            </div>
          </div>
        </div>

        <!-- Memory & conversations -->
        <div>
          <DebugNpcSocialPanel :npc="npc" />
          <p
            v-if="!npc.memory?.slots && !npc.memory?.facts?.length && !npc.conversations?.relations?.length && !npc.conversations?.topics?.length && npc.conversations?.chatty !== false"
            class="text-[11px] text-slate-500 italic px-1"
          >
            No NPC memory and no conversation settings.
          </p>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-2 px-5 py-3 border-t border-slate-800 bg-slate-950/80 shrink-0">
        <button
          type="button"
          :disabled="busy"
          class="py-1.5 px-3 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-[11px] font-bold uppercase tracking-wider cursor-pointer disabled:opacity-50"
          @click="emit('command', `/debug heal ${npc.name}`)"
        >
          Heal
        </button>
        <button
          type="button"
          :disabled="busy"
          class="py-1.5 px-3 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-300 text-[11px] font-bold uppercase tracking-wider cursor-pointer disabled:opacity-50"
          @click="emit('command', `/debug kill ${npc.name}`)"
        >
          Kill
        </button>
        <button
          v-if="npc.is_hidden"
          type="button"
          :disabled="busy"
          class="py-1.5 px-3 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-[11px] font-bold uppercase tracking-wider cursor-pointer disabled:opacity-50"
          @click="emit('command', `/debug unhide ${npc.id}`)"
        >
          Unhide
        </button>
      </div>
    </div>
  </div>
</template>
