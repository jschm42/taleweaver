<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import StatBar from './StatBar.vue'
import type { CharacterSheet } from '@/types'

const props = defineProps<{
  open: boolean
  sheet: CharacterSheet | null
}>()

const emit = defineEmits<{
  close: []
}>()

const sortedStats = computed(() => {
  if (!props.sheet?.stats) return []
  return Object.entries(props.sheet.stats).sort(([a], [b]) => a.localeCompare(b))
})

const inventoryList = computed(() => props.sheet?.inventory ?? [])
const equipmentEntries = computed(() => Object.entries(props.sheet?.equipment ?? {}))
const statusEffects = computed(() => props.sheet?.status_effects ?? [])

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl relative">
          <!-- Header -->
          <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-950/50 shrink-0">
            <h2 class="text-xl font-bold text-white flex items-center gap-3">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Character Sheet
            </h2>
            <button
              class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              @click="emit('close')"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="flex-grow overflow-y-auto p-6" v-if="sheet">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              
              <!-- Left Column: Core -->
              <div class="space-y-6">
                <!-- Identity -->
                <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
                  <h3 class="text-2xl font-bold tracking-tight text-white mb-4">{{ sheet.name || 'Unnamed' }}</h3>
                  <StatBar label="Health" :value="sheet.hp" color="crimson" />
                  <StatBar label="Stamina" :value="sheet.stamina" color="emerald" />
                  <StatBar label="Mana" :value="sheet.mana" color="sapphire" />
                </div>
                
                <!-- Status Effects -->
                <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
                  <h4 class="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-700 pb-2">Status Effects</h4>
                  <div v-if="statusEffects.length" class="flex flex-wrap gap-2">
                    <span
                      v-for="effect in statusEffects"
                      :key="effect"
                      class="px-2.5 py-1 rounded bg-red-950 border border-red-900 text-red-400 text-xs font-medium"
                    >
                      {{ effect }}
                    </span>
                  </div>
                  <p v-else class="text-sm text-slate-500 italic">No active effects.</p>
                </div>
              </div>

              <!-- Middle Column: Stats -->
              <div class="md:col-span-1">
                <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50 h-full">
                  <h4 class="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-700 pb-2">Attributes</h4>
                  <div v-if="sortedStats.length" class="space-y-3">
                    <div
                      v-for="[key, value] in sortedStats"
                      :key="key"
                      class="flex items-center justify-between"
                    >
                      <span class="text-sm text-slate-400 capitalize">{{ key }}</span>
                      <span class="text-sm font-semibold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">{{ value }}</span>
                    </div>
                  </div>
                  <p v-else class="text-sm text-slate-500 italic">No attributes recorded.</p>
                </div>
              </div>

              <!-- Right Column: Equipment -->
              <div class="space-y-6">
                <!-- Equipment -->
                <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
                  <h4 class="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-700 pb-2">Equipped</h4>
                  <div class="space-y-3">
                    <div
                      v-for="[slot, item] in equipmentEntries"
                      :key="slot"
                      class="flex flex-col"
                    >
                      <span class="text-xs text-slate-500 uppercase">{{ slot }}</span>
                      <span class="text-sm text-slate-200 mt-0.5">
                        {{ (item && typeof item === 'object' && 'name' in item) ? item.name : '—' }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Bag -->
                <div class="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
                  <h4 class="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-700 pb-2">Backpack</h4>
                  <ul v-if="inventoryList.length" class="space-y-2">
                    <li
                      v-for="(item, idx) in inventoryList"
                      :key="idx"
                      class="text-sm text-slate-300 bg-slate-900/50 px-3 py-2 rounded border border-slate-800"
                    >
                      {{ item?.name || 'Unknown item' }}
                    </li>
                  </ul>
                  <p v-else class="text-sm text-slate-500 italic">Bag is empty.</p>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else class="p-12 text-center text-slate-500">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>Character data unavailable.</p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
