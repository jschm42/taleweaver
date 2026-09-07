<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, Box } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

const props = defineProps<{
  minScenes: number | null
  maxScenes: number | null
  minItems: number | null
  maxItems: number | null
  questGenerationEnabled: boolean
  minQuests: number | null
  maxQuests: number | null
  containerGenerationEnabled: boolean
  minContainers: number | null
  maxContainers: number | null
  textLogGenerationEnabled: boolean
  minTextLogs: number | null
  maxTextLogs: number | null
  awardGenerationEnabled: boolean
  minAwards: number | null
  maxAwards: number | null
}>()

const emit = defineEmits<{
  (e: 'update:minScenes', val: number | null): void
  (e: 'update:maxScenes', val: number | null): void
  (e: 'update:minItems', val: number | null): void
  (e: 'update:maxItems', val: number | null): void
  (e: 'update:questGenerationEnabled', val: boolean): void
  (e: 'update:minQuests', val: number | null): void
  (e: 'update:maxQuests', val: number | null): void
  (e: 'update:containerGenerationEnabled', val: boolean): void
  (e: 'update:minContainers', val: number | null): void
  (e: 'update:maxContainers', val: number | null): void
  (e: 'update:textLogGenerationEnabled', val: boolean): void
  (e: 'update:minTextLogs', val: number | null): void
  (e: 'update:maxTextLogs', val: number | null): void
  (e: 'update:awardGenerationEnabled', val: boolean): void
  (e: 'update:minAwards', val: number | null): void
  (e: 'update:maxAwards', val: number | null): void
}>()

const isScenesAuto = computed(() => props.minScenes === null && props.maxScenes === null)
const isItemsAuto = computed(() => props.minItems === null && props.maxItems === null)
const isContainersAuto = computed(() => props.minContainers === null && props.maxContainers === null)
const isTextLogsAuto = computed(() => props.minTextLogs === null && props.maxTextLogs === null)
const isQuestsAuto = computed(() => props.minQuests === null && props.maxQuests === null)
const isAwardsAuto = computed(() => props.minAwards === null && props.maxAwards === null)

function toggleAuto(type: 'scenes' | 'items' | 'containers' | 'textLogs' | 'quests' | 'awards') {
  if (type === 'scenes') {
    if (isScenesAuto.value) {
      emit('update:minScenes', 3)
      emit('update:maxScenes', 6)
    } else {
      emit('update:minScenes', null)
      emit('update:maxScenes', null)
    }
  } else if (type === 'items') {
    if (isItemsAuto.value) {
      emit('update:minItems', 5)
      emit('update:maxItems', 25)
    } else {
      emit('update:minItems', null)
      emit('update:maxItems', null)
    }
  } else if (type === 'containers') {
    if (isContainersAuto.value) {
      emit('update:minContainers', 2)
      emit('update:maxContainers', 6)
    } else {
      emit('update:minContainers', null)
      emit('update:maxContainers', null)
    }
  } else if (type === 'textLogs') {
    if (isTextLogsAuto.value) {
      emit('update:minTextLogs', 1)
      emit('update:maxTextLogs', 5)
    } else {
      emit('update:minTextLogs', null)
      emit('update:maxTextLogs', null)
    }
  } else if (type === 'quests') {
    if (isQuestsAuto.value) {
      emit('update:minQuests', 3)
      emit('update:maxQuests', 5)
    } else {
      emit('update:minQuests', null)
      emit('update:maxQuests', null)
    }
  } else if (type === 'awards') {
    if (isAwardsAuto.value) {
      emit('update:minAwards', 3)
      emit('update:maxAwards', 8)
    } else {
      emit('update:minAwards', null)
      emit('update:maxAwards', null)
    }
  }
}

function updateSceneMin(val: number) {
  emit('update:minScenes', val)
  if (props.maxScenes && val > props.maxScenes) {
    emit('update:maxScenes', val)
  }
}

function updateSceneMax(val: number) {
  emit('update:maxScenes', val)
  if (props.minScenes && val < props.minScenes) {
    emit('update:minScenes', val)
  }
}

function updateItemMin(val: number) {
  emit('update:minItems', val)
  if (props.maxItems && val > props.maxItems) {
    emit('update:maxItems', val)
  }
}

function updateItemMax(val: number) {
  emit('update:maxItems', val)
  if (props.minItems && val < props.minItems) {
    emit('update:minItems', val)
  }
}

function updateContainerMin(val: number) {
  emit('update:minContainers', val)
  if (props.maxContainers && val > props.maxContainers) {
    emit('update:maxContainers', val)
  }
}

function updateContainerMax(val: number) {
  emit('update:maxContainers', val)
  if (props.minContainers && val < props.minContainers) {
    emit('update:minContainers', val)
  }
}

function updateTextLogMin(val: number) {
  emit('update:minTextLogs', val)
  if (props.maxTextLogs && val > props.maxTextLogs) {
    emit('update:maxTextLogs', val)
  }
}

function updateTextLogMax(val: number) {
  emit('update:maxTextLogs', val)
  if (props.minTextLogs && val < props.minTextLogs) {
    emit('update:minTextLogs', val)
  }
}

function updateQuestMin(val: number) {
  emit('update:minQuests', val)
  if (props.maxQuests && val > props.maxQuests) {
    emit('update:maxQuests', val)
  }
}

function updateQuestMax(val: number) {
  emit('update:maxQuests', val)
  if (props.minQuests && val < props.minQuests) {
    emit('update:minQuests', val)
  }
}

function updateAwardMin(val: number) {
  emit('update:minAwards', val)
  if (props.maxAwards && val > props.maxAwards) {
    emit('update:maxAwards', val)
  }
}

function updateAwardMax(val: number) {
  emit('update:maxAwards', val)
  if (props.minAwards && val < props.minAwards) {
    emit('update:minAwards', val)
  }
}
</script>

<template>
  <div class="p-4 sm:p-5 md:p-6 bg-slate-900/80 border border-slate-700/50 rounded-2xl space-y-5 md:space-y-6 shadow-xl relative overflow-hidden">
    <!-- Glow effect behind -->
    <div class="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="flex items-center justify-between gap-2 border-b border-white/10 pb-3 md:pb-4">
      <div class="flex items-center gap-2 sm:gap-3 min-w-0">
        <div class="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400 shrink-0">
          <Box class="w-4 h-4 sm:w-5 sm:h-5 animate-pulse" />
        </div>
        <div class="min-w-0">
          <span class="text-xs sm:text-sm font-black text-white uppercase tracking-wider block truncate">World Density & Constraints</span>
          <span class="text-[10px] text-white/40 uppercase tracking-widest">Adjust complexity bounds or set to Auto</span>
        </div>
      </div>
      <InfoPopoverButton title="World Constraints" :text="CREATE_ADVENTURE_HELP_TEXTS.sceneComplexity" />
    </div>

    <div class="space-y-4 md:space-y-6">
      <!-- Scenes Row -->
      <div class="p-3.5 sm:p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-blue-500/20">
        <div class="flex items-start sm:items-center justify-between gap-2 flex-col sm:flex-row">
          <div class="min-w-0">
            <span class="text-xs font-black uppercase tracking-widest block" :class="isScenesAuto ? 'text-white/40' : 'text-white/80'">Scenes (Locations)</span>
            <span class="text-[10px] text-white/40 uppercase tracking-wider">Number of unique areas to explore</span>
          </div>
          <button
            type="button"
            @click="toggleAuto('scenes')"
            class="self-start sm:self-auto shrink-0 px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border cursor-pointer select-none"
            :class="isScenesAuto ? 'bg-blue-500/20 border-blue-500/40 text-blue-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
          >
            {{ isScenesAuto ? 'Auto Mode' : 'Manual' }}
          </button>
        </div>

        <div v-if="isScenesAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
          ✨ AI will automatically determine optimal scene count based on your story idea.
        </div>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 pt-2">
          <div class="space-y-2">
            <div class="flex justify-between">
              <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Scenes</label>
              <span class="text-xs font-mono text-blue-400">{{ props.minScenes }}</span>
            </div>
            <input
              type="range"
              :value="props.minScenes || 3"
              @input="updateSceneMin(Number(($event.target as HTMLInputElement).value))"
              min="1"
              :max="props.maxScenes || 50"
              class="w-full accent-blue-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
            />
          </div>
          <div class="space-y-2">
            <div class="flex justify-between">
              <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Scenes</label>
              <span class="text-xs font-mono text-blue-400">{{ props.maxScenes }}</span>
            </div>
            <input
              type="range"
              :value="props.maxScenes || 6"
              @input="updateSceneMax(Number(($event.target as HTMLInputElement).value))"
              :min="props.minScenes || 1"
              max="50"
              class="w-full accent-blue-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </div>
      </div>

      <!-- Items Row -->
      <div class="p-3.5 sm:p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-lime-500/20">
        <div class="flex items-start sm:items-center justify-between gap-2 flex-col sm:flex-row">
          <div class="min-w-0">
            <span class="text-xs font-black uppercase tracking-widest block" :class="isItemsAuto ? 'text-white/40' : 'text-white/80'">Items & Objects</span>
            <span class="text-[10px] text-white/40 uppercase tracking-wider">Loot, weapons, keys, and quest items</span>
          </div>
          <button
            type="button"
            @click="toggleAuto('items')"
            class="self-start sm:self-auto shrink-0 px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border cursor-pointer select-none"
            :class="isItemsAuto ? 'bg-lime-500/20 border-lime-500/40 text-lime-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
          >
            {{ isItemsAuto ? 'Auto Mode' : 'Manual' }}
          </button>
        </div>

        <div v-if="isItemsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
          ✨ AI will generate items organically as needed for puzzles and exploration.
        </div>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 pt-2">
          <div class="space-y-2">
            <div class="flex justify-between">
              <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Items</label>
              <span class="text-xs font-mono text-lime-400">{{ props.minItems }}</span>
            </div>
            <input
              type="range"
              :value="props.minItems || 5"
              @input="updateItemMin(Number(($event.target as HTMLInputElement).value))"
              min="1"
              :max="props.maxItems || 100"
              class="w-full accent-lime-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
            />
          </div>
          <div class="space-y-2">
            <div class="flex justify-between">
              <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Items</label>
              <span class="text-xs font-mono text-lime-400">{{ props.maxItems }}</span>
            </div>
            <input
              type="range"
              :value="props.maxItems || 25"
              @input="updateItemMax(Number(($event.target as HTMLInputElement).value))"
              :min="props.minItems || 1"
              max="100"
              class="w-full accent-lime-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </div>
      </div>

      <!-- Containers Row -->
      <div class="p-3.5 sm:p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-amber-500/20">
        <div class="flex items-start sm:items-center justify-between gap-2 flex-col sm:flex-row">
          <div class="flex items-center gap-3 min-w-0">
            <input
              type="checkbox"
              :checked="props.containerGenerationEnabled"
              @change="emit('update:containerGenerationEnabled', ($event.target as HTMLInputElement).checked)"
              class="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0 h-4 w-4"
            />
            <div class="min-w-0">
              <span class="text-xs font-black uppercase tracking-widest block" :class="isContainersAuto ? 'text-white/40' : 'text-white/80'">Containers</span>
              <span class="text-[10px] text-white/40 uppercase tracking-wider">Chests, safes, and lockboxes</span>
            </div>
          </div>
          <button
            v-if="props.containerGenerationEnabled"
            type="button"
            @click="toggleAuto('containers')"
            class="self-start sm:self-auto shrink-0 px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border cursor-pointer select-none"
            :class="isContainersAuto ? 'bg-amber-500/20 border-amber-500/40 text-amber-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
          >
            {{ isContainersAuto ? 'Auto Mode' : 'Manual' }}
          </button>
        </div>

        <template v-if="props.containerGenerationEnabled">
          <div v-if="isContainersAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI will place container puzzles where appropriate.
          </div>
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Containers</label>
                <span class="text-xs font-mono text-amber-400">{{ props.minContainers }}</span>
              </div>
              <input
                type="range"
                :value="props.minContainers || 2"
                @input="updateContainerMin(Number(($event.target as HTMLInputElement).value))"
                min="1"
                :max="props.maxContainers || 20"
                class="w-full accent-amber-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Containers</label>
                <span class="text-xs font-mono text-amber-400">{{ props.maxContainers }}</span>
              </div>
              <input
                type="range"
                :value="props.maxContainers || 6"
                @input="updateContainerMax(Number(($event.target as HTMLInputElement).value))"
                :min="props.minContainers || 1"
                max="20"
                class="w-full accent-amber-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>
        </template>
      </div>

      <!-- Text Logs / Lore Row -->
      <div class="p-3.5 sm:p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-cyan-500/20">
        <div class="flex items-start sm:items-center justify-between gap-2 flex-col sm:flex-row">
          <div class="flex items-center gap-3 min-w-0">
            <input
              type="checkbox"
              :checked="props.textLogGenerationEnabled"
              @change="emit('update:textLogGenerationEnabled', ($event.target as HTMLInputElement).checked)"
              class="rounded bg-slate-800 border-slate-700 text-cyan-500 focus:ring-0 h-4 w-4"
            />
            <div class="min-w-0">
              <span class="text-xs font-black uppercase tracking-widest block" :class="isTextLogsAuto ? 'text-white/40' : 'text-white/80'">Lore & Documents</span>
              <span class="text-[10px] text-white/40 uppercase tracking-wider">Readable logs, journals, and tablets</span>
            </div>
          </div>
          <button
            v-if="props.textLogGenerationEnabled"
            type="button"
            @click="toggleAuto('textLogs')"
            class="self-start sm:self-auto shrink-0 px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border cursor-pointer select-none"
            :class="isTextLogsAuto ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
          >
            {{ isTextLogsAuto ? 'Auto Mode' : 'Manual' }}
          </button>
        </div>

        <template v-if="props.textLogGenerationEnabled">
          <div v-if="isTextLogsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI will write environmental lore documents to enrich world backstory.
          </div>
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Documents</label>
                <span class="text-xs font-mono text-cyan-400">{{ props.minTextLogs }}</span>
              </div>
              <input
                type="range"
                :value="props.minTextLogs || 1"
                @input="updateTextLogMin(Number(($event.target as HTMLInputElement).value))"
                min="1"
                :max="props.maxTextLogs || 20"
                class="w-full accent-cyan-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Documents</label>
                <span class="text-xs font-mono text-cyan-400">{{ props.maxTextLogs }}</span>
              </div>
              <input
                type="range"
                :value="props.maxTextLogs || 5"
                @input="updateTextLogMax(Number(($event.target as HTMLInputElement).value))"
                :min="props.minTextLogs || 1"
                max="20"
                class="w-full accent-cyan-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>
        </template>
      </div>

      <!-- Quests Row -->
      <div class="p-3.5 sm:p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-purple-500/20">
        <div class="flex items-start sm:items-center justify-between gap-2 flex-col sm:flex-row">
          <div class="flex items-center gap-3 min-w-0">
            <input
              type="checkbox"
              :checked="props.questGenerationEnabled"
              @change="emit('update:questGenerationEnabled', ($event.target as HTMLInputElement).checked)"
              class="rounded bg-slate-800 border-slate-700 text-purple-500 focus:ring-0 h-4 w-4"
            />
            <div class="min-w-0">
              <span class="text-xs font-black uppercase tracking-widest block" :class="isQuestsAuto ? 'text-white/40' : 'text-white/80'">Quests & Objectives</span>
              <span class="text-[10px] text-white/40 uppercase tracking-wider">Missions and story challenges</span>
            </div>
          </div>
          <button
            v-if="props.questGenerationEnabled"
            type="button"
            @click="toggleAuto('quests')"
            class="self-start sm:self-auto shrink-0 px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border cursor-pointer select-none"
            :class="isQuestsAuto ? 'bg-purple-500/20 border-purple-500/40 text-purple-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
          >
            {{ isQuestsAuto ? 'Auto Mode' : 'Manual' }}
          </button>
        </div>

        <template v-if="props.questGenerationEnabled">
          <div v-if="isQuestsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI will generate appropriate main and side quests matching your plotline.
          </div>
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Quests</label>
                <span class="text-xs font-mono text-purple-400">{{ props.minQuests }}</span>
              </div>
              <input
                type="range"
                :value="props.minQuests || 3"
                @input="updateQuestMin(Number(($event.target as HTMLInputElement).value))"
                min="1"
                :max="props.maxQuests || 15"
                class="w-full accent-purple-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Quests</label>
                <span class="text-xs font-mono text-purple-400">{{ props.maxQuests }}</span>
              </div>
              <input
                type="range"
                :value="props.maxQuests || 5"
                @input="updateQuestMax(Number(($event.target as HTMLInputElement).value))"
                :min="props.minQuests || 1"
                max="15"
                class="w-full accent-purple-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>
        </template>
      </div>

      <!-- Awards Row -->
      <div class="p-3.5 sm:p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-indigo-500/20">
        <div class="flex items-start sm:items-center justify-between gap-2 flex-col sm:flex-row">
          <div class="flex items-center gap-3 min-w-0">
            <input
              type="checkbox"
              :checked="props.awardGenerationEnabled"
              @change="emit('update:awardGenerationEnabled', ($event.target as HTMLInputElement).checked)"
              class="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0 h-4 w-4"
            />
            <div class="min-w-0">
              <span class="text-xs font-black uppercase tracking-widest block" :class="isAwardsAuto ? 'text-white/40' : 'text-white/80'">Awards & Trophies</span>
              <span class="text-[10px] text-white/40 uppercase tracking-wider">Achievements earned throughout adventure</span>
            </div>
          </div>
          <button
            v-if="props.awardGenerationEnabled"
            type="button"
            @click="toggleAuto('awards')"
            class="self-start sm:self-auto shrink-0 px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border cursor-pointer select-none"
            :class="isAwardsAuto ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
          >
            {{ isAwardsAuto ? 'Auto Mode' : 'Manual' }}
          </button>
        </div>

        <template v-if="props.awardGenerationEnabled">
          <div v-if="isAwardsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI determines optimal achievements and awards based on quest complexity.
          </div>
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Awards</label>
                <span class="text-xs font-mono text-indigo-400">{{ props.minAwards }}</span>
              </div>
              <input
                type="range"
                :value="props.minAwards || 3"
                @input="updateAwardMin(Number(($event.target as HTMLInputElement).value))"
                min="0"
                :max="props.maxAwards || 20"
                class="w-full accent-indigo-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Awards</label>
                <span class="text-xs font-mono text-indigo-400">{{ props.maxAwards }}</span>
              </div>
              <input
                type="range"
                :value="props.maxAwards || 8"
                @input="updateAwardMax(Number(($event.target as HTMLInputElement).value))"
                :min="props.minAwards || 0"
                max="20"
                class="w-full accent-indigo-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>
        </template>
      </div>

      <!-- Warning for large worlds -->
      <div v-if="!isScenesAuto && props.maxScenes && props.maxScenes > 15" class="flex gap-2 sm:gap-3 items-start p-3 rounded-xl bg-amber-500/5 border border-amber-500/10 text-[10px] text-amber-400 uppercase tracking-wider leading-relaxed">
        <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
        <span>Large worlds (&gt; 15 scenes) may feel sparse. Walkthrough steps, items, and NPCs do not automatically scale up due to AI model limits.</span>
      </div>
    </div>
  </div>
</template>
