<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import type { GameSession } from '@/types'
import {
  Play,
  FileText,
  Copy,
  Download,
  Trash2,
  Clock,
  Compass,
  Sword,
  BookOpen,
  MessageSquare,
  MoreVertical,
  Loader2,
  AlertTriangle,
  Image
} from 'lucide-vue-next'
import { formatCatalogLabel } from '@/composables/usePortalFilters'

const props = defineProps<{
  sessions: GameSession[]
  allFilteredSessions: GameSession[]
  hasMore?: boolean
  totalFilteredCount?: number
}>()

const emit = defineEmits<{
  (e: 'resume', gameId: string): void
  (e: 'delete', gameId: string, title: string): void
  (e: 'copy', gameId: string): void
  (e: 'edit-note', gameId: string, currentNote: string): void
  (e: 'export', gameId: string): void
  (e: 'switch-to-templates'): void
  (e: 'load-more'): void
}>()

const activeMenuId = ref<string | null>(null)
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null
let scrollContainer: HTMLElement | null = null

function toggleMenu(id: string, ev: MouseEvent) {
  ev.stopPropagation()
  activeMenuId.value = activeMenuId.value === id ? null : id
}

function handleGlobalClick() {
  activeMenuId.value = null
}

function handleScroll() {
  if (!scrollContainer) return
  if (scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight < 400) {
    emit('load-more')
  }
}

onMounted(() => {
  window.addEventListener('click', handleGlobalClick)

  if (sentinelRef.value) {
    scrollContainer = sentinelRef.value.closest('.overflow-y-auto') as HTMLElement | null
    if (scrollContainer) {
      scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
    }
    observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          emit('load-more')
        }
      },
      { root: scrollContainer, rootMargin: '400px' }
    )
    observer.observe(sentinelRef.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('click', handleGlobalClick)
  if (scrollContainer) {
    scrollContainer.removeEventListener('scroll', handleScroll)
  }
  if (observer) {
    observer.disconnect()
    observer = null
  }
})

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Recently'
  const d = new Date(dateStr)
  return d.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  })
}

function getToneLabel(session: GameSession): string {
  return formatCatalogLabel(session.selected_tone)
}

function getStyleLabels(session: GameSession): string[] {
  if (!session.selected_image_styles || !Array.isArray(session.selected_image_styles)) return []
  return session.selected_image_styles
    .map((s) => formatCatalogLabel(s))
    .filter(Boolean)
}

function getModeBadge(mode?: string): { label: string; class: string; icon: any } {
  const normalized = (mode || 'rpg').toLowerCase() === 'strict' ? 'rpg' : (mode || 'rpg').toLowerCase()
  if (normalized === 'story') {
    return { label: 'Story', class: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30', icon: BookOpen }
  }
  if (normalized === 'chat') {
    return { label: 'Chat', class: 'bg-purple-500/10 text-purple-300 border-purple-500/30', icon: MessageSquare }
  }
  return { label: 'RPG', class: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30', icon: Sword }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Empty State -->
    <div
      v-if="props.sessions.length === 0"
      class="rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur p-12 text-center flex flex-col items-center gap-4"
    >
      <div class="w-14 h-14 rounded-full bg-white/5 flex items-center justify-center text-slate-500">
        <i class="ra ra-pawn text-2xl"></i>
      </div>
      <div>
        <h3 class="text-base font-bold text-white mb-1">No sessions found</h3>
        <p class="text-xs sm:text-sm text-slate-400 max-w-sm">
          No game sessions match your current filters, or you haven't started any playthroughs yet.
        </p>
      </div>
      <button
        @click="$emit('switch-to-templates')"
        class="mt-2 px-5 py-2.5 rounded-xl bg-aether-primary/20 border border-aether-primary/40 text-aether-primary font-bold text-xs uppercase tracking-wider hover:bg-aether-primary/30 transition-all flex items-center gap-2"
      >
        <Compass class="w-4 h-4" />
        <span>Browse Adventure Library</span>
      </button>
    </div>

    <!-- Table Container -->
    <div v-else class="rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-md overflow-hidden shadow-2xl">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs sm:text-sm text-slate-300">
          <thead class="bg-black/40 border-b border-white/10 text-[11px] uppercase tracking-wider text-slate-400 font-bold">
            <tr>
              <th scope="col" class="py-3 px-3 sm:px-4 w-16">Cover</th>
              <th scope="col" class="py-3 px-3 sm:px-4 min-w-[200px]">Playthrough</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden sm:table-cell">Scene</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden md:table-cell">Mode</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden lg:table-cell">Tone & Style</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden xl:table-cell">Status</th>
              <th scope="col" class="py-3 px-3 sm:px-4 text-right min-w-[150px]">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            <tr
              v-for="session in props.sessions"
              :key="session.game_id"
              class="hover:bg-white/[0.03] transition-colors group"
            >
              <!-- Cover Column -->
              <td class="py-3 px-3 sm:px-4">
                <div class="w-12 h-16 sm:w-14 sm:h-18 rounded-lg overflow-hidden bg-black/50 border border-white/10 shrink-0 relative">
                  <img
                    v-if="session.image_url"
                    :src="session.image_url"
                    :alt="session.adventure_title"
                    class="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-300"
                    loading="lazy"
                  />
                  <div v-else class="w-full h-full flex items-center justify-center text-slate-600">
                    <Image class="w-5 h-5" />
                  </div>
                </div>
              </td>

              <!-- Title & Meta Column -->
              <td class="py-3 px-3 sm:px-4">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-white text-sm sm:text-base group-hover:text-aether-primary transition-colors">
                    {{ session.adventure_title }}
                  </span>
                  <span v-if="session.adventure_version" class="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-400 font-mono">
                    v{{ session.adventure_version }}
                  </span>
                </div>
                
                <!-- Status Note / Last Activity -->
                <div class="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
                  <span v-if="session.status_note" class="line-clamp-1 italic text-slate-300">
                    "{{ session.status_note }}"
                  </span>
                  <span v-else class="text-slate-500">No notes</span>
                  <button
                    @click="$emit('edit-note', session.game_id, session.status_note || '')"
                    class="text-[11px] text-aether-primary hover:underline ml-1"
                    title="Edit Note"
                  >
                    Edit Note
                  </button>
                </div>

                <div class="flex items-center gap-2 mt-1 text-[11px] text-slate-500">
                  <span>Started {{ formatDate(session.created_at) }}</span>
                  <span v-if="session.is_legacy_format" class="text-amber-400 flex items-center gap-1">
                    <AlertTriangle class="w-3 h-3" />
                    Legacy Format
                  </span>
                </div>
              </td>

              <!-- Scene & Time Column -->
              <td class="py-3 px-3 sm:px-4 hidden sm:table-cell">
                <div class="space-y-0.5">
                  <span class="font-semibold text-slate-200 block">
                    {{ session.current_scene_name || 'Exploring...' }}
                  </span>
                  <div class="flex items-center gap-1.5 text-[11px] text-slate-400">
                    <Clock class="w-3.5 h-3.5" />
                    <span>Turn {{ session.in_game_time || 0 }}</span>
                  </div>
                </div>
              </td>

              <!-- Mode Column -->
              <td class="py-3 px-3 sm:px-4 hidden md:table-cell">
                <span
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border"
                  :class="getModeBadge(session.rule_enforcement_mode).class"
                >
                  <component :is="getModeBadge(session.rule_enforcement_mode).icon" class="w-3.5 h-3.5" />
                  {{ getModeBadge(session.rule_enforcement_mode).label }}
                </span>
              </td>

              <!-- Tone & Style Column -->
              <td class="py-3 px-3 sm:px-4 hidden lg:table-cell">
                <div class="flex flex-col gap-1 items-start">
                  <span
                    v-if="getToneLabel(session)"
                    class="px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] font-semibold"
                  >
                    {{ getToneLabel(session) }}
                  </span>
                  <div v-if="getStyleLabels(session).length > 0" class="flex flex-wrap gap-1">
                    <span
                      v-for="(styleName, sIdx) in getStyleLabels(session).slice(0, 1)"
                      :key="sIdx"
                      class="px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/30 text-purple-300 text-[11px] font-semibold"
                    >
                      {{ styleName }}
                    </span>
                  </div>
                  <span v-if="!getToneLabel(session) && getStyleLabels(session).length === 0" class="text-slate-600 text-xs">
                    -
                  </span>
                </div>
              </td>

              <!-- Status Column -->
              <td class="py-3 px-3 sm:px-4 hidden xl:table-cell">
                <span
                  class="px-2.5 py-1 rounded-full text-[11px] font-black uppercase tracking-wider inline-block"
                  :class="{
                    'bg-amber-500/20 text-amber-300 border border-amber-500/30': session.is_paused && (!session.status || session.status === 'active'),
                    'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30': !session.is_paused && (!session.status || session.status === 'active'),
                    'bg-red-500/20 text-red-300 border border-red-500/30': session.status === 'game_over',
                    'bg-emerald-600/30 text-emerald-100 border border-emerald-400/30': session.status === 'completed'
                  }"
                >
                  {{
                    session.status === 'game_over' ? 'Defeated' :
                    session.status === 'completed' ? 'Victory' :
                    (session.is_paused ? 'Paused' : 'Active')
                  }}
                </span>
              </td>

              <!-- Actions Column -->
              <td class="py-3 px-3 sm:px-4 text-right">
                <div class="flex items-center justify-end gap-1.5">
                  <!-- Resume Button -->
                  <button
                    @click="$emit('resume', session.game_id)"
                    class="px-3 py-1.5 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-bold uppercase tracking-wider hover:bg-emerald-500/30 transition-all flex items-center gap-1.5 shadow-sm shadow-emerald-500/20"
                    title="Resume Playthrough"
                  >
                    <Play class="w-3.5 h-3.5 fill-current" />
                    <span>Resume</span>
                  </button>

                  <!-- Note Button -->
                  <button
                    @click="$emit('edit-note', session.game_id, session.status_note || '')"
                    class="p-1.5 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 transition-all"
                    title="Edit Status Note"
                  >
                    <FileText class="w-4 h-4" />
                  </button>

                  <!-- More Actions Dropdown -->
                  <div class="relative">
                    <button
                      @click="toggleMenu(session.game_id, $event)"
                      class="p-1.5 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all"
                      title="More actions"
                    >
                      <MoreVertical class="w-4 h-4" />
                    </button>

                    <!-- Dropdown Menu -->
                    <div
                      v-if="activeMenuId === session.game_id"
                      class="absolute right-0 top-full mt-1.5 w-48 rounded-xl bg-slate-900 border border-white/15 p-1.5 shadow-2xl z-30 divide-y divide-white/5"
                    >
                      <div class="py-1">
                        <button
                          @click="$emit('export', session.game_id); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-300 hover:bg-white/10 hover:text-white flex items-center gap-2"
                        >
                          <Download class="w-3.5 h-3.5" />
                          <span>Export (.ads)</span>
                        </button>
                        <button
                          @click="$emit('copy', session.game_id); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-300 hover:bg-white/10 hover:text-white flex items-center gap-2"
                        >
                          <Copy class="w-3.5 h-3.5" />
                          <span>Duplicate Session</span>
                        </button>
                      </div>
                      <div class="pt-1">
                        <button
                          @click="$emit('delete', session.game_id, session.adventure_title); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-red-400 hover:bg-red-500/20 flex items-center gap-2"
                        >
                          <Trash2 class="w-3.5 h-3.5" />
                          <span>Delete Session</span>
                        </button>
                      </div>
                    </div>
                  </div>

                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Infinite Scroll Sentinel & Loader -->
      <div ref="sentinelRef" class="py-4 px-6 flex items-center justify-center border-t border-white/5 bg-black/20">
        <div v-if="props.hasMore" class="flex items-center gap-2 text-xs text-slate-400">
          <Loader2 class="w-4 h-4 animate-spin text-aether-primary" />
          <span>Loading more sessions (showing {{ props.sessions.length }} of {{ props.totalFilteredCount }})...</span>
        </div>
        <div v-else-if="props.sessions.length > 0" class="text-xs text-slate-500">
          All {{ props.sessions.length }} sessions loaded
        </div>
      </div>
    </div>
  </div>
</template>
