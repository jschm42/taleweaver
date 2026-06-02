<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  show: boolean
  sceneLabel?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', itemType: string): void
}>()

const searchQuery = ref('')

interface ItemTypeOption {
  type: string
  label: string
  description: string
  icon: string
  color: string
  borderColor: string
}

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
    description: 'An item that can be combined with others to create new items.',
    icon: 'ra-cycle',
    color: 'text-violet-300',
    borderColor: 'border-violet-500/20',
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

function handleSelect(type: string) {
  emit('select', type)
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
                <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">Create New Item</h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">
                  Scene: {{ sceneLabel || 'Current Scene' }}
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
                placeholder="Search item types..."
              />
            </div>
          </div>

          <!-- Grid -->
          <div class="p-6 overflow-y-auto">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <button
                v-for="itemType in filteredTypes"
                :key="itemType.type"
                class="group relative flex items-start gap-3 p-4 rounded-xl border bg-slate-950/40 text-left transition-all duration-200 hover:bg-slate-800/60 hover:border-emerald-500/30 hover:shadow-lg hover:shadow-emerald-900/10"
                :class="[itemType.borderColor]"
                @click="handleSelect(itemType.type)"
              >
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

          <!-- Footer -->
          <div class="p-4 border-t border-white/5 flex justify-end">
            <button
              @click="emit('close')"
              class="px-6 py-2.5 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors"
            >
              Cancel
            </button>
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