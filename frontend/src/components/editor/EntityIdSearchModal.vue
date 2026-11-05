<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import {
  Search,
  X,
  Hash,
  Package,
  Users,
  Scroll,
  MapPin,
  DoorOpen,
  ToggleLeft,
  Copy,
  Check,
  Quote,
  CornerDownLeft,
} from 'lucide-vue-next'

export interface GameEntityOption {
  id: string
  name?: string
  type?: 'OBJECT' | 'NPC' | 'QUEST' | 'SCENE' | 'EXIT' | 'SWITCH' | string
  itemType?: string
  sceneLabel?: string
  description?: string
  imageUrl?: string | null
}

const props = withDefaults(
  defineProps<{
    show: boolean
    entities?: GameEntityOption[]
  }>(),
  {
    show: false,
    entities: () => [],
  }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', id: string, entity?: GameEntityOption): void
}>()

const searchQuery = ref('')
const selectedCategory = ref<string>('all')
const selectedIndex = ref<number>(0)
const wrapInQuotes = ref<boolean>(false)
const copiedId = ref<string | null>(null)

const searchInputRef = ref<HTMLInputElement | null>(null)
const listContainerRef = ref<HTMLDivElement | null>(null)
const itemRefs = ref<(HTMLElement | null)[]>([])

function normalizeType(type?: string, itemType?: string): string {
  const t = String(type || '').toUpperCase()
  if (t === 'OBJECT' && String(itemType || '').toUpperCase() === 'SWITCH') {
    return 'SWITCH'
  }
  return t || 'OBJECT'
}

const CATEGORIES = [
  { id: 'all', label: 'All', icon: Hash },
  { id: 'OBJECT', label: 'Items', icon: Package },
  { id: 'NPC', label: 'NPCs', icon: Users },
  { id: 'QUEST', label: 'Quests', icon: Scroll },
  { id: 'SCENE', label: 'Scenes', icon: MapPin },
  { id: 'EXIT', label: 'Exits', icon: DoorOpen },
  { id: 'SWITCH', label: 'Switches', icon: ToggleLeft },
] as const

const categoryCounts = computed(() => {
  const counts: Record<string, number> = {
    all: props.entities.length,
    OBJECT: 0,
    NPC: 0,
    QUEST: 0,
    SCENE: 0,
    EXIT: 0,
    SWITCH: 0,
  }
  for (const item of props.entities) {
    const norm = normalizeType(item.type, item.itemType)
    if (counts[norm] !== undefined) {
      counts[norm]++
    }
  }
  return counts
})

const filteredEntities = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const cat = selectedCategory.value

  return props.entities.filter((entity) => {
    const normType = normalizeType(entity.type, entity.itemType)
    if (cat !== 'all' && normType !== cat) {
      return false
    }

    if (!q) return true

    const haystack = [
      entity.id,
      entity.name,
      entity.type,
      entity.itemType,
      entity.sceneLabel,
      entity.description,
    ]
      .filter(Boolean)
      .map((val) => String(val).toLowerCase())
      .join(' ')

    return haystack.includes(q)
  })
})

watch([searchQuery, selectedCategory], () => {
  selectedIndex.value = 0
})

watch(
  () => props.show,
  (isOpen) => {
    if (isOpen) {
      searchQuery.value = ''
      selectedIndex.value = 0
      itemRefs.value = []
      nextTick(() => {
        searchInputRef.value?.focus()
        searchInputRef.value?.select()
      })
    }
  }
)

watch(selectedIndex, (idx) => {
  nextTick(() => {
    const el = itemRefs.value[idx]
    if (el && listContainerRef.value) {
      el.scrollIntoView({ block: 'nearest' })
    }
  })
})

function handleCategorySelect(catId: string) {
  selectedCategory.value = catId
  nextTick(() => {
    searchInputRef.value?.focus()
  })
}

function navigateDown() {
  const len = filteredEntities.value.length
  if (len === 0) return
  selectedIndex.value = (selectedIndex.value + 1) % len
}

function navigateUp() {
  const len = filteredEntities.value.length
  if (len === 0) return
  selectedIndex.value = (selectedIndex.value - 1 + len) % len
}

function getFormattedId(id: string, quote?: boolean): string {
  const shouldQuote = quote !== undefined ? quote : wrapInQuotes.value
  return shouldQuote ? `"${id}"` : id
}

function selectEntity(entity: GameEntityOption, quote?: boolean) {
  const formatted = getFormattedId(entity.id, quote)
  emit('select', formatted, entity)
}

function selectCurrent(e?: KeyboardEvent) {
  if (filteredEntities.value.length === 0) return
  const entity = filteredEntities.value[selectedIndex.value]
  if (!entity) return
  const isShift = e?.shiftKey
  const quote = isShift ? !wrapInQuotes.value : wrapInQuotes.value
  selectEntity(entity, quote)
}

async function copyToClipboard(id: string, e: Event) {
  e.stopPropagation()
  try {
    await navigator.clipboard.writeText(id)
    copiedId.value = id
    setTimeout(() => {
      if (copiedId.value === id) copiedId.value = null
    }, 1500)
  } catch {
    // clipboard write failed silently
  }
}

function getBadgeMeta(type?: string, itemType?: string) {
  const norm = normalizeType(type, itemType)
  switch (norm) {
    case 'NPC':
      return { label: 'NPC', color: 'bg-sky-500/15 text-sky-300 border-sky-500/30', icon: Users }
    case 'QUEST':
      return { label: 'Quest', color: 'bg-purple-500/15 text-purple-300 border-purple-500/30', icon: Scroll }
    case 'SCENE':
      return { label: 'Scene', color: 'bg-amber-500/15 text-amber-300 border-amber-500/30', icon: MapPin }
    case 'EXIT':
      return { label: 'Exit', color: 'bg-teal-500/15 text-teal-300 border-teal-500/30', icon: DoorOpen }
    case 'SWITCH':
      return { label: 'Switch', color: 'bg-lime-500/15 text-lime-300 border-lime-500/30', icon: ToggleLeft }
    case 'OBJECT':
    default:
      return {
        label: itemType ? String(itemType).toUpperCase() : 'Item',
        color: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
        icon: Package,
      }
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="show"
        class="fixed inset-0 z-[200] flex items-center justify-center p-4 backdrop-blur-xl bg-slate-950/70 select-none"
        @click.self="emit('close')"
        @keydown.esc="emit('close')"
      >
        <div
          class="modal-content w-full max-w-2xl bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden max-h-[85vh] flex flex-col"
        >
          <!-- Header -->
          <div class="px-5 py-4 border-b border-white/10 flex items-center justify-between bg-slate-900/80">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0">
                <Hash class="w-4 h-4 text-amber-400" />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-black text-white uppercase tracking-wider">
                    Insert Game Entity ID
                  </h3>
                  <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-white/5 font-bold">
                    {{ filteredEntities.length }} {{ filteredEntities.length === 1 ? 'match' : 'matches' }}
                  </span>
                </div>
                <p class="text-[11px] text-slate-400">
                  Search items, NPCs, quests, scenes or switches and insert into script.
                </p>
              </div>
            </div>
            <button
              type="button"
              @click="emit('close')"
              class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
              title="Close (Esc)"
            >
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Search Input & Quick Controls -->
          <div class="p-4 border-b border-white/5 bg-slate-950/40 space-y-3">
            <div class="relative">
              <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                class="w-full bg-slate-900 border border-white/10 rounded-xl pl-10 pr-9 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500/50 transition-colors"
                placeholder="Search by ID, name, scene, or type... (↑↓ to navigate, Enter to insert)"
                @keydown.down.prevent="navigateDown"
                @keydown.up.prevent="navigateUp"
                @keydown.enter.prevent="selectCurrent"
                @keydown.esc.prevent="emit('close')"
              />
              <button
                v-if="searchQuery"
                type="button"
                @click="searchQuery = ''; searchInputRef?.focus()"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>

            <!-- Categories & Options row -->
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <!-- Category Filter Chips -->
              <div class="flex items-center gap-1.5 overflow-x-auto py-0.5 max-w-full">
                <button
                  v-for="cat in CATEGORIES"
                  :key="cat.id"
                  type="button"
                  @click="handleCategorySelect(cat.id)"
                  :class="[
                    'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors shrink-0',
                    selectedCategory === cat.id
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : 'bg-slate-800/60 text-slate-400 border-white/5 hover:text-slate-200 hover:bg-slate-800',
                  ]"
                >
                  <component :is="cat.icon" class="w-3 h-3" />
                  <span>{{ cat.label }}</span>
                  <span
                    :class="[
                      'text-[9px] px-1.5 py-0.2 rounded-full font-mono font-bold',
                      selectedCategory === cat.id ? 'bg-amber-500/30 text-amber-200' : 'bg-black/30 text-slate-400',
                    ]"
                  >
                    {{ categoryCounts[cat.id] ?? 0 }}
                  </span>
                </button>
              </div>

              <!-- Quote Toggle -->
              <label class="flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-200 cursor-pointer shrink-0 ml-auto select-none">
                <input
                  type="checkbox"
                  v-model="wrapInQuotes"
                  class="rounded bg-slate-900 border-white/10 text-amber-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                />
                <Quote class="w-3 h-3 text-amber-400" />
                <span>Wrap in quotes (<code class="text-amber-300 font-mono">"..."</code>)</span>
              </label>
            </div>
          </div>

          <!-- Entity Results List -->
          <div ref="listContainerRef" class="p-3 overflow-y-auto max-h-[50vh] space-y-1.5">
            <div
              v-if="filteredEntities.length === 0"
              class="text-center py-10 text-slate-500 text-xs space-y-2"
            >
              <Hash class="w-8 h-8 text-slate-600 mx-auto" />
              <p class="font-medium text-slate-400">No matching entities found.</p>
              <p class="text-[11px] text-slate-600">
                Try a different keyword or reset the category filter.
              </p>
              <button
                v-if="searchQuery || selectedCategory !== 'all'"
                type="button"
                @click="searchQuery = ''; selectedCategory = 'all'"
                class="mt-2 px-3 py-1 text-[11px] text-amber-400 hover:text-amber-300 underline"
              >
                Clear search and filters
              </button>
            </div>

            <div
              v-for="(entity, idx) in filteredEntities"
              :key="entity.id"
              :ref="(el) => (itemRefs[idx] = el as HTMLElement)"
              :class="[
                'group flex items-center justify-between gap-3 p-2.5 rounded-xl border transition-all cursor-pointer',
                selectedIndex === idx
                  ? 'bg-amber-500/15 border-amber-500/50 shadow-sm'
                  : 'bg-slate-950/40 border-white/5 hover:bg-slate-800/60 hover:border-white/10',
              ]"
              @click="selectEntity(entity)"
              @mouseenter="selectedIndex = idx"
            >
              <!-- Left info -->
              <div class="flex items-center gap-2.5 min-w-0 flex-1">
                <div class="w-8 h-8 rounded-lg bg-slate-900 border border-white/10 flex items-center justify-center shrink-0 overflow-hidden">
                  <img
                    v-if="entity.imageUrl"
                    :src="entity.imageUrl"
                    :alt="entity.name || entity.id"
                    class="w-full h-full object-cover"
                  />
                  <component
                    v-else
                    :is="getBadgeMeta(entity.type, entity.itemType).icon"
                    class="w-4 h-4 text-slate-400 group-hover:text-amber-300 transition-colors"
                  />
                </div>

                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-mono text-xs font-bold text-amber-400 tracking-wide">
                      {{ wrapInQuotes ? `"${entity.id}"` : entity.id }}
                    </span>
                    <span
                      v-if="entity.name && entity.name !== entity.id"
                      class="text-xs text-white font-medium truncate"
                    >
                      {{ entity.name }}
                    </span>
                    <span
                      :class="[
                        'text-[9px] font-bold px-1.5 py-0.2 rounded border uppercase font-mono tracking-wider',
                        getBadgeMeta(entity.type, entity.itemType).color,
                      ]"
                    >
                      {{ getBadgeMeta(entity.type, entity.itemType).label }}
                    </span>
                  </div>

                  <div class="text-[10px] text-slate-400 truncate mt-0.5 flex items-center gap-1.5">
                    <span v-if="entity.sceneLabel" class="text-slate-500">
                      📍 {{ entity.sceneLabel }}
                    </span>
                    <span v-if="entity.sceneLabel && entity.description" class="text-slate-600">•</span>
                    <span v-if="entity.description" class="truncate">
                      {{ entity.description }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Right action buttons -->
              <div class="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  @click="copyToClipboard(entity.id, $event)"
                  class="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-white/5 transition-colors"
                  :title="copiedId === entity.id ? 'Copied!' : 'Copy ID to clipboard'"
                >
                  <Check v-if="copiedId === entity.id" class="w-3.5 h-3.5 text-emerald-400" />
                  <Copy v-else class="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  @click.stop="selectEntity(entity)"
                  :class="[
                    'flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold border transition-colors',
                    selectedIndex === idx
                      ? 'bg-amber-500 text-slate-950 border-amber-400'
                      : 'bg-slate-800 text-slate-300 border-white/5 group-hover:border-amber-500/30 group-hover:text-amber-300',
                  ]"
                >
                  <span>Insert</span>
                  <CornerDownLeft class="w-2.5 h-2.5" />
                </button>
              </div>
            </div>
          </div>

          <!-- Footer with keyboard shortcuts -->
          <div class="px-5 py-3 border-t border-white/10 bg-slate-950/60 flex items-center justify-between text-[11px] text-slate-500">
            <div class="flex items-center gap-3 hidden sm:flex">
              <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-white/10 text-slate-300 font-mono text-[10px]">↑</kbd> <kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-white/10 text-slate-300 font-mono text-[10px]">↓</kbd> navigate</span>
              <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-white/10 text-slate-300 font-mono text-[10px]">Enter</kbd> insert</span>
              <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-white/10 text-slate-300 font-mono text-[10px]">Shift+Enter</kbd> quote toggle</span>
              <span><kbd class="px-1.5 py-0.5 rounded bg-slate-800 border border-white/10 text-slate-300 font-mono text-[10px]">Esc</kbd> cancel</span>
            </div>
            <div class="flex items-center justify-end w-full sm:w-auto">
              <button
                type="button"
                @click="emit('close')"
                class="px-4 py-1.5 rounded-lg text-slate-400 hover:text-white font-bold text-xs uppercase tracking-wider transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-content {
  animation: modalScaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-leave-active .modal-content {
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  transform: scale(0.96);
}

@keyframes modalScaleIn {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(12px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
