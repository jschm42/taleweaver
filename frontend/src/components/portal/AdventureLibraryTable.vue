<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import type { AdventureTemplateSummary } from '@/types'
import {
  Play,
  Edit3,
  MoreVertical,
  Download,
  Trash2,
  Image,
  RefreshCw,
  Sword,
  BookOpen,
  MessageSquare,
  Sparkles,
  AlertCircle,
  Plus,
  Compass,
  ArrowDownToLine,
  Loader2
} from 'lucide-vue-next'
import { formatCatalogLabel } from '@/composables/usePortalFilters'
import PendingAdventureCard from './PendingAdventureCard.vue'

const props = defineProps<{
  visibleTemplates: AdventureTemplateSummary[]
  allFilteredTemplates: AdventureTemplateSummary[]
  pendingCards: any[]
  isSeeding: boolean
  loadingWordIndex: number
  isStartingSession?: boolean
  startingSessionTemplateId?: string | null
  updatingTemplateIds?: Set<string>
  hasMore?: boolean
  totalFilteredCount?: number
}>()

const emit = defineEmits<{
  (e: 'create'): void
  (e: 'generate-world'): void
  (e: 'import-samples'): void
  (e: 'remove-failed-pending', adventureId: string, kind: 'creation' | 'import'): void
  (e: 'cancel-pending', adventureId: string): void
  (e: 'start-session', templateId: string): void
  (e: 'update-adventure', templateId: string): void
  (e: 'migrate', template: any): void
  (e: 'cover', templateId: string): void
  (e: 'edit', templateId: string): void
  (e: 'export-adz', templateId: string, title: string): void
  (e: 'export-adv', templateId: string, title: string): void
  (e: 'delete', templateId: string, title: string): void
  (e: 'dismiss-warning', templateId: string): void
  (e: 'click-pending', pending: any): void
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

function handleGlobalClick(ev: MouseEvent) {
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

function getToneLabel(template: AdventureTemplateSummary): string {
  return formatCatalogLabel(template.selected_tone)
}

function getStyleLabels(template: AdventureTemplateSummary): string[] {
  if (!template.selected_image_styles || !Array.isArray(template.selected_image_styles)) return []
  return template.selected_image_styles
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
    <!-- Quick Action Bar in Table View -->
    <div class="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl bg-white/5 border border-white/10">
      <div class="flex items-center gap-2">
        <button
          @click="$emit('create')"
          class="px-3.5 py-2 rounded-xl bg-aether-primary/20 border border-aether-primary/40 text-aether-primary text-xs font-bold uppercase tracking-wider hover:bg-aether-primary/30 transition-all flex items-center gap-2 shadow-lg shadow-aether-primary/10"
        >
          <Plus class="w-4 h-4" />
          <span>New Adventure</span>
        </button>

        <button
          @click="$emit('generate-world')"
          class="px-3.5 py-2 rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-300 text-xs font-bold uppercase tracking-wider hover:bg-purple-500/30 transition-all flex items-center gap-2 shadow-lg shadow-purple-500/10"
        >
          <Sparkles class="w-4 h-4" />
          <span>Generate World</span>
        </button>

        <button
          v-if="!props.isSeeding"
          @click="$emit('import-samples')"
          class="px-3.5 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300 text-xs font-bold uppercase tracking-wider hover:bg-white/10 hover:text-white transition-all flex items-center gap-2"
        >
          <Compass class="w-4 h-4" />
          <span>Import Samples</span>
        </button>
      </div>

      <div v-if="props.isSeeding" class="flex items-center gap-2 text-xs text-aether-primary font-bold">
        <Loader2 class="w-4 h-4 animate-spin" />
        <span>Importing sample tales...</span>
      </div>
    </div>

    <!-- Pending Creations Cards (if any) -->
    <div v-if="props.pendingCards.length > 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
      <PendingAdventureCard
        v-for="pending in props.pendingCards"
        :key="`pending-${pending.adventureId}`"
        :pending="pending"
        :loading-word-index="props.loadingWordIndex"
        @remove-failed="(id, kind) => $emit('remove-failed-pending', id, kind)"
        @cancel="(id) => $emit('cancel-pending', id)"
        @click="$emit('click-pending', pending)"
      />
    </div>

    <!-- Empty State -->
    <div
      v-if="props.visibleTemplates.length === 0 && props.pendingCards.length === 0"
      class="rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur p-12 text-center flex flex-col items-center gap-4"
    >
      <div class="w-14 h-14 rounded-full bg-white/5 flex items-center justify-center text-slate-500">
        <BookOpen class="w-7 h-7" />
      </div>
      <div>
        <h3 class="text-base font-bold text-white mb-1">No adventures found</h3>
        <p class="text-xs sm:text-sm text-slate-400 max-w-sm">
          No adventure templates match your active filters, or your library is currently empty.
        </p>
      </div>
    </div>

    <!-- Table Container -->
    <div v-else class="rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-md overflow-hidden shadow-2xl">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs sm:text-sm text-slate-300">
          <thead class="bg-black/40 border-b border-white/10 text-[11px] uppercase tracking-wider text-slate-400 font-bold">
            <tr>
              <th scope="col" class="py-3 px-3 sm:px-4 w-16">Cover</th>
              <th scope="col" class="py-3 px-3 sm:px-4 min-w-[200px]">Adventure</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden sm:table-cell">Mode</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden md:table-cell">Tone & Style</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden lg:table-cell">Quests</th>
              <th scope="col" class="py-3 px-3 sm:px-4 hidden xl:table-cell">Status</th>
              <th scope="col" class="py-3 px-3 sm:px-4 text-right min-w-[140px]">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            <tr
              v-for="template in props.visibleTemplates"
              :key="template.template_id"
              class="hover:bg-white/[0.03] transition-colors group"
            >
              <!-- Cover Column -->
              <td class="py-3 px-3 sm:px-4">
                <div class="w-12 h-16 sm:w-14 sm:h-18 rounded-lg overflow-hidden bg-black/50 border border-white/10 shrink-0 relative">
                  <img
                    v-if="template.image_url"
                    :src="template.image_url"
                    :alt="template.title"
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
                    {{ template.title }}
                  </span>
                  <span v-if="template.version" class="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-400 font-mono">
                    v{{ template.version }}
                  </span>
                </div>
                <p v-if="template.teaser" class="text-xs text-slate-400 line-clamp-1 mt-0.5 max-w-md">
                  {{ template.teaser }}
                </p>
                <div class="flex items-center gap-2 mt-1 text-[11px] text-slate-500">
                  <span v-if="template.creator">By {{ template.creator }}</span>
                  <span v-if="template.has_update" class="text-cyan-400 font-bold flex items-center gap-1">
                    • Update v{{ template.available_version }} available
                  </span>
                </div>
              </td>

              <!-- Mode Column -->
              <td class="py-3 px-3 sm:px-4 hidden sm:table-cell">
                <span
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border"
                  :class="getModeBadge(template.rule_enforcement_mode).class"
                >
                  <component :is="getModeBadge(template.rule_enforcement_mode).icon" class="w-3.5 h-3.5" />
                  {{ getModeBadge(template.rule_enforcement_mode).label }}
                </span>
              </td>

              <!-- Tone & Style Column -->
              <td class="py-3 px-3 sm:px-4 hidden md:table-cell">
                <div class="flex flex-col gap-1 items-start">
                  <span
                    v-if="getToneLabel(template)"
                    class="px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] font-semibold"
                  >
                    {{ getToneLabel(template) }}
                  </span>
                  <div v-if="getStyleLabels(template).length > 0" class="flex flex-wrap gap-1">
                    <span
                      v-for="(styleName, sIdx) in getStyleLabels(template).slice(0, 1)"
                      :key="sIdx"
                      class="px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/30 text-purple-300 text-[11px] font-semibold"
                    >
                      {{ styleName }}
                    </span>
                    <span v-if="getStyleLabels(template).length > 1" class="text-[10px] text-slate-500 self-center">
                      +{{ getStyleLabels(template).length - 1 }}
                    </span>
                  </div>
                  <span v-if="!getToneLabel(template) && getStyleLabels(template).length === 0" class="text-slate-600 text-xs">
                    -
                  </span>
                </div>
              </td>

              <!-- Quests Column -->
              <td class="py-3 px-3 sm:px-4 hidden lg:table-cell">
                <div v-if="(template.quest_count || 0) > 0" class="space-y-1">
                  <div class="flex items-center justify-between text-xs text-slate-400">
                    <span>{{ template.completed_quest_count || 0 }} / {{ template.quest_count }}</span>
                    <span>{{ template.progress || 0 }}%</span>
                  </div>
                  <div class="w-24 h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      class="h-full bg-emerald-500 rounded-full transition-all"
                      :style="{ width: `${template.progress || 0}%` }"
                    ></div>
                  </div>
                </div>
                <span v-else class="text-slate-600 text-xs">No quests</span>
              </td>

              <!-- Status Column -->
              <td class="py-3 px-3 sm:px-4 hidden xl:table-cell">
                <div class="flex items-center gap-2">
                  <span
                    v-if="template.has_update"
                    class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 animate-pulse"
                  >
                    Update
                  </span>
                  <span
                    v-else-if="template.is_ready"
                    class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                  >
                    Ready
                  </span>
                  <span
                    v-else
                    class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30"
                  >
                    {{ template.creation_status || 'Draft' }}
                  </span>
                </div>
              </td>

              <!-- Actions Column -->
              <td class="py-3 px-3 sm:px-4 text-right">
                <div class="flex items-center justify-end gap-1.5">
                  <!-- Migrate Button (if legacy format) -->
                  <button
                    v-if="template.is_legacy_format || !template.can_start"
                    @click="$emit('migrate', template)"
                    class="px-3 py-1.5 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-300 hover:text-white text-xs font-bold uppercase tracking-wider hover:bg-amber-500/30 transition-all flex items-center gap-1.5 shadow-sm shadow-amber-500/20 cursor-pointer"
                    title="Migrate Adventure format"
                  >
                    <i class="ra ra-wrench text-xs"></i>
                    <span class="hidden sm:inline">Migrate</span>
                  </button>

                  <!-- Play / Start Button -->
                  <button
                    v-else
                    @click="$emit('start-session', template.template_id)"
                    :disabled="props.isStartingSession"
                    class="px-3 py-1.5 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-bold uppercase tracking-wider hover:bg-emerald-500/30 transition-all flex items-center gap-1.5 shadow-sm shadow-emerald-500/20 disabled:opacity-50"
                    title="Play Adventure"
                  >
                    <Play class="w-3.5 h-3.5 fill-current" />
                    <span class="hidden sm:inline">Play</span>
                  </button>

                  <!-- Update Button (if update available) -->
                  <button
                    v-if="template.has_update"
                    @click="$emit('update-adventure', template.template_id)"
                    :disabled="props.updatingTemplateIds?.has(template.template_id)"
                    class="p-1.5 rounded-xl bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/30 transition-all"
                    title="Update to newest version"
                  >
                    <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': props.updatingTemplateIds?.has(template.template_id) }" />
                  </button>

                  <!-- Edit Button -->
                  <button
                    @click="$emit('edit', template.template_id)"
                    class="p-1.5 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:text-white hover:bg-white/10 transition-all"
                    title="Edit Adventure Blueprint"
                  >
                    <Edit3 class="w-4 h-4" />
                  </button>

                  <!-- More Actions Dropdown -->
                  <div class="relative">
                    <button
                      @click="toggleMenu(template.template_id, $event)"
                      class="p-1.5 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all"
                      title="More actions"
                    >
                      <MoreVertical class="w-4 h-4" />
                    </button>

                    <!-- Dropdown Menu -->
                    <div
                      v-if="activeMenuId === template.template_id"
                      class="absolute right-0 top-full mt-1.5 w-48 rounded-xl bg-slate-900 border border-white/15 p-1.5 shadow-2xl z-30 divide-y divide-white/5"
                    >
                      <div class="py-1">
                        <button
                          v-if="template.is_legacy_format || !template.can_start"
                          @click="$emit('migrate', template); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-amber-300 hover:bg-amber-500/10 hover:text-white flex items-center gap-2"
                        >
                          <i class="ra ra-wrench text-xs"></i>
                          <span>Migrate Format</span>
                        </button>
                        <button
                          @click="$emit('cover', template.template_id); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-300 hover:bg-white/10 hover:text-white flex items-center gap-2"
                        >
                          <Image class="w-3.5 h-3.5" />
                          <span>Generate Cover</span>
                        </button>
                        <button
                          @click="$emit('export-adz', template.template_id, template.title); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-300 hover:bg-white/10 hover:text-white flex items-center gap-2"
                        >
                          <Download class="w-3.5 h-3.5" />
                          <span>Export (.adz)</span>
                        </button>
                        <button
                          @click="$emit('export-adv', template.template_id, template.title); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-slate-300 hover:bg-white/10 hover:text-white flex items-center gap-2"
                        >
                          <Download class="w-3.5 h-3.5" />
                          <span>Export (.adv)</span>
                        </button>
                      </div>
                      <div class="pt-1">
                        <button
                          @click="$emit('delete', template.template_id, template.title); activeMenuId = null"
                          class="w-full text-left px-3 py-1.5 rounded-lg text-xs text-red-400 hover:bg-red-500/20 flex items-center gap-2"
                        >
                          <Trash2 class="w-3.5 h-3.5" />
                          <span>Delete Adventure</span>
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
          <span>Loading more adventures (showing {{ props.visibleTemplates.length }} of {{ props.totalFilteredCount }})...</span>
        </div>
        <div v-else-if="props.visibleTemplates.length > 0" class="text-xs text-slate-500">
          All {{ props.visibleTemplates.length }} adventures loaded
        </div>
      </div>
    </div>
  </div>
</template>
