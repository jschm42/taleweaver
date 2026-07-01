<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  show: boolean
  sceneLabel?: string
  mode?: 'create' | 'change'
  currentItemName?: string
  currentItemType?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', itemType: string): void
}>()

const searchQuery = ref('')
// In change-mode, the user must explicitly confirm a target type. Holds the
// user's currently-staged selection (empty until first pick) until they press
// "Confirm Change". Always reset when the modal opens.
const stagedTargetType = ref<string>('')

watch(
  () => props.show,
  (isOpen) => {
    if (isOpen) {
      searchQuery.value = ''
      stagedTargetType.value = ''
    }
  },
)

interface ItemTypeOption {
  type: string
  label: string
  description: string
  icon: string
  color: string
  borderColor: string
  deprecated?: boolean
}

const normalizedMode = computed(() => props.mode || 'create')
const isChangeMode = computed(() => normalizedMode.value === 'change')

const normalizedCurrentType = computed(() =>
  String(props.currentItemType || '').toUpperCase(),
)

const normalizedStagedType = computed(() => String(stagedTargetType.value || '').toUpperCase())

const stagedOption = computed(() => {
  if (!normalizedStagedType.value) return null
  return itemTypes.find((t) => t.type.toUpperCase() === normalizedStagedType.value) || null
})

const canConfirmChange = computed(
  () =>
    isChangeMode.value &&
    normalizedStagedType.value.length > 0 &&
    normalizedStagedType.value !== normalizedCurrentType.value,
)

const itemTypes: ItemTypeOption[] = [
  {
    type: 'DEFAULT',
    label: 'Default',
    description: 'A standard item. Whether it can be picked up is controlled by the Portable flag.',
    icon: 'ra-key',
    color: 'text-slate-200',
    borderColor: 'border-white/10',
  },
  {
    type: 'CONSUMABLE',
    label: 'Consumable',
    description: 'A potion, food, or item that is used up when consumed.',
    icon: 'ra-potion',
    color: 'text-rose-300',
    borderColor: 'border-rose-500/20',
  },
  {
    type: 'WEARABLE',
    label: 'Wearable',
    description: 'Armor, clothing, or accessories that can be equipped.',
    icon: 'ra-helmet',
    color: 'text-sky-300',
    borderColor: 'border-sky-500/20',
  },
  {
    type: 'WEAPON',
    label: 'Weapon',
    description: 'A sword, bow, or any weapon used in combat.',
    icon: 'ra-sword',
    color: 'text-red-300',
    borderColor: 'border-red-500/20',
  },
  {
    type: 'COMBINABLE',
    label: 'Combinable',
    description: 'Deprecated — use Constructable. Legacy combine marker without deterministic engine behavior.',
    icon: 'ra-cycle',
    color: 'text-violet-300',
    borderColor: 'border-violet-500/20',
    deprecated: true,
  },
  {
    type: 'CONSTRUCTABLE',
    label: 'Constructable',
    description: 'A hidden item that materializes when all its ingredients (min. 2) are combined. Ingredients are consumed automatically.',
    icon: 'ra-hammer',
    color: 'text-orange-300',
    borderColor: 'border-orange-500/20',
  },
  {
    type: 'READABLE',
    label: 'Readable',
    description: 'A scroll, book, sign, or note with readable text.',
    icon: 'ra-scroll-unfurled',
    color: 'text-cyan-300',
    borderColor: 'border-cyan-500/20',
  },
  {
    type: 'CONTAINER',
    label: 'Container',
    description: 'A chest, crate, or bag that can hold other items.',
    icon: 'ra-chest',
    color: 'text-amber-300',
    borderColor: 'border-amber-500/20',
  },
  {
    type: 'SWITCH',
    label: 'Switch',
    description: 'A lever, button, or mechanism that toggles world state.',
    icon: 'ra-lightning-bolt',
    color: 'text-lime-300',
    borderColor: 'border-lime-500/20',
  },
]

const filteredTypes = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return itemTypes
  return itemTypes.filter(
    (t) =>
      t.type.toLowerCase().includes(q) ||
      t.label.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q)
  )
})

function isCurrentType(type: string): boolean {
  return isChangeMode.value && type.toUpperCase() === normalizedCurrentType.value
}

function isStagedType(type: string): boolean {
  return isChangeMode.value && type.toUpperCase() === normalizedStagedType.value
}

function handleSelect(type: string) {
  if (isChangeMode.value) {
    // Picking the current type is a soft no-op — the user hasn't picked a target yet.
    if (isCurrentType(type)) {
      stagedTargetType.value = ''
      return
    }
    // Stage the selection; the parent only learns about it on explicit confirm.
    stagedTargetType.value = type
    return
  }
  emit('select', type)
  emit('close')
}

function handleConfirmChange() {
  if (!canConfirmChange.value) return
  emit('select', normalizedStagedType.value)
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="modal-content w-full max-w-3xl bg-slate-900 border border-white/10 rounded-[2rem] shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
          <!-- Header -->
          <div class="p-6 pb-4 border-b border-white/5">
            <div class="flex justify-between items-center mb-4">
              <div class="space-y-1">
                <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">
                  {{ isChangeMode ? 'Change Item Type' : 'Create New Item' }}
                </h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">
                  <template v-if="isChangeMode">
                    Item: <span class="text-slate-200">{{ currentItemName || 'this item' }}</span>
                    <span v-if="currentItemType" class="ml-2 text-amber-400/80">(currently {{ currentItemType }})</span>
                  </template>
                  <template v-else>
                    Scene: {{ sceneLabel || 'Current Scene' }}
                  </template>
                </p>
              </div>
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>
            <!-- Search -->
            <div class="relative">
              <i class="ra ra-search absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
              <input
                v-model="searchQuery"
                class="w-full bg-black/40 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:border-emerald-500/50 outline-none transition-all"
                :placeholder="isChangeMode ? 'Search target types…' : 'Search item types...'"
              />
            </div>
            <!-- Change-mode warning -->
            <div
              v-if="isChangeMode"
              class="mt-4 px-3 py-2 rounded-lg border border-amber-500/40 bg-amber-500/10 text-[11px] text-amber-200/90 leading-relaxed flex items-start gap-2"
              role="alert"
            >
              <i class="ra ra-warning text-amber-400 mt-0.5 shrink-0"></i>
              <span>
                Important — switching the type will reset type-specific metadata on this item
                (e.g. text content for READABLE, lock/unlock data for CONTAINER, switch states for SWITCH,
                consumable effects). Type-specific fields will need to be re-entered afterwards.
              </span>
            </div>
          </div>

          <!-- Grid -->
          <div class="p-6 overflow-y-auto">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <button
                v-for="itemType in filteredTypes"
                :key="itemType.type"
                class="group relative flex items-start gap-3 p-4 rounded-xl border bg-slate-950/40 text-left transition-all duration-200"
                :class="[
                  itemType.borderColor,
                  isCurrentType(itemType.type) ? 'opacity-50 cursor-not-allowed ring-1 ring-amber-500/40' : '',
                  isStagedType(itemType.type)
                    ? 'border-emerald-400 bg-emerald-500/15 shadow-lg shadow-emerald-900/30 ring-1 ring-emerald-400/50'
                    : isChangeMode
                      ? 'hover:bg-slate-800/60 hover:border-emerald-500/30'
                      : 'hover:bg-slate-800/60 hover:border-emerald-500/30 hover:shadow-lg hover:shadow-emerald-900/10',
                ]"
                :disabled="isCurrentType(itemType.type)"
                @click="handleSelect(itemType.type)"
              >
                <span
                  v-if="isStagedType(itemType.type)"
                  class="absolute top-2 right-2 text-[9px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded-full bg-emerald-500 text-slate-950 flex items-center gap-1 shadow-md"
                >
                  <i class="ra ra-checkmark text-[8px]"></i> New
                </span>
                <span
                  v-else-if="isCurrentType(itemType.type)"
                  class="absolute top-2 right-2 text-[9px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded-full bg-amber-500/80 text-slate-950 shadow-md"
                >
                  Current
                </span>
                <span
                  v-if="itemType.deprecated && !isStagedType(itemType.type)"
                  class="absolute top-2 right-2 text-[9px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded-full bg-red-500/80 text-slate-950 shadow-md"
                  :class="{ '!bg-amber-500/80': isCurrentType(itemType.type) }"
                >
                  Deprecated
                </span>
                <div
                  class="flex items-center justify-center w-10 h-10 rounded-lg bg-slate-900 border border-white/10 shrink-0 transition-colors group-hover:border-emerald-500/30"
                >
                  <i :class="[itemType.icon, itemType.color, 'text-lg']"></i>
                </div>
                <div class="min-w-0">
                  <div class="flex items-center gap-2 mb-0.5">
                    <span class="text-xs font-black text-white uppercase tracking-wider">{{ itemType.label }}</span>
                    <span class="text-[9px] font-mono text-slate-600 uppercase tracking-wider">{{ itemType.type }}</span>
                  </div>
                  <p class="text-[11px] text-slate-400 leading-relaxed">{{ itemType.description }}</p>
                </div>
              </button>
            </div>
            <div v-if="filteredTypes.length === 0" class="text-center py-8 text-slate-500 text-sm">
              No item types match your search.
            </div>
          </div>

          <!-- Footer — change mode shows staged target + Confirm; create mode keeps the original Cancel-only flow. -->
          <div class="p-4 border-t border-white/5 flex items-center justify-between gap-3">
            <div class="min-w-0">
              <template v-if="isChangeMode">
                <div v-if="stagedOption" class="flex items-center gap-2 text-xs">
                  <span class="text-slate-500 font-black uppercase tracking-widest text-[10px]">Staged Target</span>
                  <span class="px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 font-mono uppercase text-[10px] tracking-wider">
                    {{ stagedOption.label }} — {{ stagedOption.type }}
                  </span>
                  <span class="text-slate-500 text-[10px] truncate">from current <span class="text-amber-300/80 font-mono">{{ normalizedCurrentType || '—' }}</span></span>
                </div>
                <p v-else class="text-[11px] text-slate-500">Pick a target type to confirm. The current type is disabled.</p>
              </template>
              <template v-else>
                <span class="text-[11px] text-slate-500">Pick a type — it will be applied when you click the button.</span>
              </template>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <button
                @click="emit('close')"
                class="px-5 py-2 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors"
              >
                Cancel
              </button>
              <button
                v-if="isChangeMode"
                @click="handleConfirmChange"
                :disabled="!canConfirmChange"
                :title="!canConfirmChange ? 'Pick a target type first' : 'Apply this type change to the item'"
                class="px-5 py-2 rounded-lg font-black uppercase text-xs tracking-widest transition-colors"
                :class="
                  canConfirmChange
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-lg'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                "
              >
                <i class="ra ra-checkmark mr-1"></i>
                Confirm Change
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
  transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-content {
  animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-leave-active .modal-content {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  transform: scale(0.95);
}

@keyframes modalScaleIn {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(40px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>