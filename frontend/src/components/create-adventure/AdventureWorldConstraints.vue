<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, Box, Check } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

const props = defineProps<{
  minScenes: number | null
  maxScenes: number | null
  minItems: number | null
  maxItems: number | null
  minSequences: number | null
  maxSequences: number | null
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
  scriptsGenerationEnabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:minScenes', val: number | null): void
  (e: 'update:maxScenes', val: number | null): void
  (e: 'update:minItems', val: number | null): void
  (e: 'update:maxItems', val: number | null): void
  (e: 'update:minSequences', val: number | null): void
  (e: 'update:maxSequences', val: number | null): void
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
  (e: 'update:scriptsGenerationEnabled', val: boolean): void
}>()

const isScenesAuto = computed(() => props.minScenes === null && props.maxScenes === null)
const isItemsAuto = computed(() => props.minItems === null && props.maxItems === null)
const isSequencesAuto = computed(() => props.minSequences === null && props.maxSequences === null)
const isContainersAuto = computed(() => props.minContainers === null && props.maxContainers === null)
const isTextLogsAuto = computed(() => props.minTextLogs === null && props.maxTextLogs === null)
const isQuestsAuto = computed(() => props.minQuests === null && props.maxQuests === null)
const isAwardsAuto = computed(() => props.minAwards === null && props.maxAwards === null)

function toggleAuto(type: 'scenes' | 'items' | 'sequences' | 'containers' | 'textLogs' | 'quests' | 'awards') {
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
  } else if (type === 'sequences') {
    if (isSequencesAuto.value) {
      emit('update:minSequences', 3)
      emit('update:maxSequences', 5)
    } else {
      emit('update:minSequences', null)
      emit('update:maxSequences', null)
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

function clamp(val: number, min: number, max: number) {
  return Math.max(min, Math.min(max, isNaN(val) ? min : val))
}

function updateSceneMin(val: number) {
  val = clamp(val, 1, 20)
  emit('update:minScenes', val)
  if (props.maxScenes && val > props.maxScenes) emit('update:maxScenes', val)
}
function updateSceneMax(val: number) {
  val = clamp(val, 1, 20)
  emit('update:maxScenes', val)
  if (props.minScenes && val < props.minScenes) emit('update:minScenes', val)
}

function updateItemMin(val: number) {
  val = clamp(val, 0, 50)
  emit('update:minItems', val)
  if (props.maxItems && val > props.maxItems) emit('update:maxItems', val)
}
function updateItemMax(val: number) {
  val = clamp(val, 0, 50)
  emit('update:maxItems', val)
  if (props.minItems && val < props.minItems) emit('update:minItems', val)
}

function updateSequenceMin(val: number) {
  val = clamp(val, 1, 15)
  emit('update:minSequences', val)
  if (props.maxSequences && val > props.maxSequences) emit('update:maxSequences', val)
}
function updateSequenceMax(val: number) {
  val = clamp(val, 1, 15)
  emit('update:maxSequences', val)
  if (props.minSequences && val < props.minSequences) emit('update:minSequences', val)
}

function updateContainerMin(val: number) {
  val = clamp(val, 0, 20)
  emit('update:minContainers', val)
  if (props.maxContainers && val > props.maxContainers) emit('update:maxContainers', val)
}
function updateContainerMax(val: number) {
  val = clamp(val, 0, 20)
  emit('update:maxContainers', val)
  if (props.minContainers && val < props.minContainers) emit('update:minContainers', val)
}

function updateTextLogMin(val: number) {
  val = clamp(val, 0, 20)
  emit('update:minTextLogs', val)
  if (props.maxTextLogs && val > props.maxTextLogs) emit('update:maxTextLogs', val)
}
function updateTextLogMax(val: number) {
  val = clamp(val, 0, 20)
  emit('update:maxTextLogs', val)
  if (props.minTextLogs && val < props.minTextLogs) emit('update:minTextLogs', val)
}

function updateQuestMin(val: number) {
  val = clamp(val, 0, 10)
  emit('update:minQuests', val)
  if (props.maxQuests && val > props.maxQuests) emit('update:maxQuests', val)
}
function updateQuestMax(val: number) {
  val = clamp(val, 0, 10)
  emit('update:maxQuests', val)
  if (props.minQuests && val < props.minQuests) emit('update:minQuests', val)
}

function updateAwardMin(val: number) {
  val = clamp(val, 0, 10)
  emit('update:minAwards', val)
  if (props.maxAwards && val > props.maxAwards) emit('update:maxAwards', val)
}
function updateAwardMax(val: number) {
  val = clamp(val, 0, 10)
  emit('update:maxAwards', val)
  if (props.minAwards && val < props.minAwards) emit('update:minAwards', val)
}
</script>

<template>
  <div class="p-4 sm:p-5 md:p-6 bg-slate-900/80 border border-slate-700/50 rounded-2xl space-y-4 md:space-y-5 shadow-xl relative overflow-hidden">
    <!-- Glow effect behind -->
    <div class="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>

    <div class="flex items-center justify-between gap-2 border-b border-white/10 pb-3 md:pb-4">
      <div class="flex items-center gap-2 sm:gap-3 min-w-0">
        <div class="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400 shrink-0">
          <Box class="w-4 h-4 sm:w-5 sm:h-5 animate-pulse" />
        </div>
        <div class="min-w-0">
          <span class="text-xs sm:text-sm font-black text-white uppercase tracking-wider block truncate">World Density & Constraints</span>
          <span class="text-[10px] text-white/40 uppercase tracking-widest">Configure generation asset bounds</span>
        </div>
      </div>
      <InfoPopoverButton title="World Constraints" :text="CREATE_ADVENTURE_HELP_TEXTS.sceneComplexity" />
    </div>

    <div class="overflow-x-auto custom-scrollbar -mx-4 sm:mx-0 px-4 sm:px-0">
      <table class="w-full text-left min-w-[500px]">
        <thead>
          <tr class="border-b border-white/10">
            <th class="pb-2 text-[10px] font-black uppercase tracking-widest text-slate-400 w-8 text-center">En</th>
            <th class="pb-2 text-[10px] font-black uppercase tracking-widest text-slate-400 pl-2">Category</th>
            <th class="pb-2 text-[10px] font-black uppercase tracking-widest text-slate-400 text-center w-20">Auto</th>
            <th class="pb-2 text-[10px] font-black uppercase tracking-widest text-slate-400 pl-4 w-40">Min/Max</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-white/5">
          <!-- Sequences -->
          <tr class="hover:bg-slate-800/30 transition-colors">
            <td class="py-2.5 text-center">
              <div class="w-4 h-4 mx-auto rounded border border-white/20 bg-slate-800 flex items-center justify-center text-white/40 cursor-not-allowed">
                <Check class="w-3 h-3 text-white/40" />
              </div>
            </td>
            <td class="py-2.5 pl-2">
              <span class="text-xs font-bold uppercase tracking-widest text-white/90 block">Sequences</span>
              <span class="text-[10px] text-white/40 block">Linear story chapters</span>
            </td>
            <td class="py-2.5 text-center">
              <button
                type="button"
                @click="toggleAuto('sequences')"
                class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider transition-all border cursor-pointer select-none"
                :class="isSequencesAuto ? 'bg-orange-500/20 border-orange-500/40 text-orange-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
              >
                {{ isSequencesAuto ? 'Auto' : 'Man' }}
              </button>
            </td>
            <td class="py-2.5 pl-4">
              <div v-if="!isSequencesAuto" class="flex items-center gap-2">
                <input type="number" :value="props.minSequences || 3" @input="updateSequenceMin(Number(($event.target as HTMLInputElement).value))" min="1" :max="props.maxSequences || 15" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-orange-500/50 outline-none text-white font-mono" />
                <span class="text-white/30 text-xs">-</span>
                <input type="number" :value="props.maxSequences || 5" @input="updateSequenceMax(Number(($event.target as HTMLInputElement).value))" :min="props.minSequences || 1" max="15" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-orange-500/50 outline-none text-white font-mono" />
              </div>
              <div v-else class="text-[10px] text-white/30 italic">Determined by AI</div>
            </td>
          </tr>
          
          <!-- Scenes -->
          <tr class="hover:bg-slate-800/30 transition-colors">
            <td class="py-2.5 text-center">
              <div class="w-4 h-4 mx-auto rounded border border-white/20 bg-slate-800 flex items-center justify-center text-white/40 cursor-not-allowed">
                <Check class="w-3 h-3 text-white/40" />
              </div>
            </td>
            <td class="py-2.5 pl-2">
              <span class="text-xs font-bold uppercase tracking-widest text-white/90 block">Scenes</span>
              <span class="text-[10px] text-white/40 block">Locations to explore</span>
            </td>
            <td class="py-2.5 text-center">
              <button
                type="button"
                @click="toggleAuto('scenes')"
                class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider transition-all border cursor-pointer select-none"
                :class="isScenesAuto ? 'bg-blue-500/20 border-blue-500/40 text-blue-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
              >
                {{ isScenesAuto ? 'Auto' : 'Man' }}
              </button>
            </td>
            <td class="py-2.5 pl-4">
              <div v-if="!isScenesAuto" class="flex items-center gap-2">
                <input type="number" :value="props.minScenes || 3" @input="updateSceneMin(Number(($event.target as HTMLInputElement).value))" min="1" :max="props.maxScenes || 50" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-blue-500/50 outline-none text-white font-mono" />
                <span class="text-white/30 text-xs">-</span>
                <input type="number" :value="props.maxScenes || 6" @input="updateSceneMax(Number(($event.target as HTMLInputElement).value))" :min="props.minScenes || 1" max="50" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-blue-500/50 outline-none text-white font-mono" />
              </div>
              <div v-else class="text-[10px] text-white/30 italic">Determined by AI</div>
            </td>
          </tr>

          <!-- Items -->
          <tr class="hover:bg-slate-800/30 transition-colors">
            <td class="py-2.5 text-center">
              <div class="w-4 h-4 mx-auto rounded border border-white/20 bg-slate-800 flex items-center justify-center text-white/40 cursor-not-allowed">
                <Check class="w-3 h-3 text-white/40" />
              </div>
            </td>
            <td class="py-2.5 pl-2">
              <span class="text-xs font-bold uppercase tracking-widest text-white/90 block">Items</span>
              <span class="text-[10px] text-white/40 block">Loot, weapons, keys</span>
            </td>
            <td class="py-2.5 text-center">
              <button
                type="button"
                @click="toggleAuto('items')"
                class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider transition-all border cursor-pointer select-none"
                :class="isItemsAuto ? 'bg-lime-500/20 border-lime-500/40 text-lime-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
              >
                {{ isItemsAuto ? 'Auto' : 'Man' }}
              </button>
            </td>
            <td class="py-2.5 pl-4">
              <div v-if="!isItemsAuto" class="flex items-center gap-2">
                <input type="number" :value="props.minItems || 5" @input="updateItemMin(Number(($event.target as HTMLInputElement).value))" min="1" :max="props.maxItems || 100" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-lime-500/50 outline-none text-white font-mono" />
                <span class="text-white/30 text-xs">-</span>
                <input type="number" :value="props.maxItems || 25" @input="updateItemMax(Number(($event.target as HTMLInputElement).value))" :min="props.minItems || 1" max="100" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-lime-500/50 outline-none text-white font-mono" />
              </div>
              <div v-else class="text-[10px] text-white/30 italic">Determined by AI</div>
            </td>
          </tr>

          <!-- Sidequests -->
          <tr class="hover:bg-slate-800/30 transition-colors">
            <td class="py-2.5 text-center">
              <input
                type="checkbox"
                :checked="props.questGenerationEnabled"
                @change="emit('update:questGenerationEnabled', ($event.target as HTMLInputElement).checked)"
                class="rounded bg-slate-800 border-slate-700 text-purple-500 focus:ring-0 h-4 w-4 block mx-auto cursor-pointer"
              />
            </td>
            <td class="py-2.5 pl-2" :class="!props.questGenerationEnabled ? 'opacity-50' : ''">
              <span class="text-xs font-bold uppercase tracking-widest text-white/90 block">Sidequests</span>
              <span class="text-[10px] text-white/40 block">Optional missions</span>
            </td>
            <td class="py-2.5 text-center">
              <button
                v-if="props.questGenerationEnabled"
                type="button"
                @click="toggleAuto('quests')"
                class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider transition-all border cursor-pointer select-none"
                :class="isQuestsAuto ? 'bg-purple-500/20 border-purple-500/40 text-purple-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
              >
                {{ isQuestsAuto ? 'Auto' : 'Man' }}
              </button>
            </td>
            <td class="py-2.5 pl-4" :class="!props.questGenerationEnabled ? 'opacity-50' : ''">
              <div v-if="props.questGenerationEnabled">
                <div v-if="!isQuestsAuto" class="flex items-center gap-2">
                  <input type="number" :value="props.minQuests || 3" @input="updateQuestMin(Number(($event.target as HTMLInputElement).value))" min="1" :max="props.maxQuests || 15" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-purple-500/50 outline-none text-white font-mono" />
                  <span class="text-white/30 text-xs">-</span>
                  <input type="number" :value="props.maxQuests || 5" @input="updateQuestMax(Number(($event.target as HTMLInputElement).value))" :min="props.minQuests || 1" max="15" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-purple-500/50 outline-none text-white font-mono" />
                </div>
                <div v-else class="text-[10px] text-white/30 italic">Determined by AI</div>
              </div>
            </td>
          </tr>

          <!-- Containers -->
          <tr class="hover:bg-slate-800/30 transition-colors">
            <td class="py-2.5 text-center">
              <input
                type="checkbox"
                :checked="props.containerGenerationEnabled"
                @change="emit('update:containerGenerationEnabled', ($event.target as HTMLInputElement).checked)"
                class="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0 h-4 w-4 block mx-auto cursor-pointer"
              />
            </td>
            <td class="py-2.5 pl-2" :class="!props.containerGenerationEnabled ? 'opacity-50' : ''">
              <span class="text-xs font-bold uppercase tracking-widest text-white/90 block">Containers</span>
              <span class="text-[10px] text-white/40 block">Chests and lockboxes</span>
            </td>
            <td class="py-2.5 text-center">
              <button
                v-if="props.containerGenerationEnabled"
                type="button"
                @click="toggleAuto('containers')"
                class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider transition-all border cursor-pointer select-none"
                :class="isContainersAuto ? 'bg-amber-500/20 border-amber-500/40 text-amber-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
              >
                {{ isContainersAuto ? 'Auto' : 'Man' }}
              </button>
            </td>
            <td class="py-2.5 pl-4" :class="!props.containerGenerationEnabled ? 'opacity-50' : ''">
              <div v-if="props.containerGenerationEnabled">
                <div v-if="!isContainersAuto" class="flex items-center gap-2">
                  <input type="number" :value="props.minContainers || 2" @input="updateContainerMin(Number(($event.target as HTMLInputElement).value))" min="1" :max="props.maxContainers || 20" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-amber-500/50 outline-none text-white font-mono" />
                  <span class="text-white/30 text-xs">-</span>
                  <input type="number" :value="props.maxContainers || 6" @input="updateContainerMax(Number(($event.target as HTMLInputElement).value))" :min="props.minContainers || 1" max="20" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-amber-500/50 outline-none text-white font-mono" />
                </div>
                <div v-else class="text-[10px] text-white/30 italic">Determined by AI</div>
              </div>
            </td>
          </tr>

          <!-- Text Logs -->
          <tr class="hover:bg-slate-800/30 transition-colors">
            <td class="py-2.5 text-center">
              <input
                type="checkbox"
                :checked="props.textLogGenerationEnabled"
                @change="emit('update:textLogGenerationEnabled', ($event.target as HTMLInputElement).checked)"
                class="rounded bg-slate-800 border-slate-700 text-cyan-500 focus:ring-0 h-4 w-4 block mx-auto cursor-pointer"
              />
            </td>
            <td class="py-2.5 pl-2" :class="!props.textLogGenerationEnabled ? 'opacity-50' : ''">
              <span class="text-xs font-bold uppercase tracking-widest text-white/90 block">Lore</span>
              <span class="text-[10px] text-white/40 block">Readable documents</span>
            </td>
            <td class="py-2.5 text-center">
              <button
                v-if="props.textLogGenerationEnabled"
                type="button"
                @click="toggleAuto('textLogs')"
                class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider transition-all border cursor-pointer select-none"
                :class="isTextLogsAuto ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
              >
                {{ isTextLogsAuto ? 'Auto' : 'Man' }}
              </button>
            </td>
            <td class="py-2.5 pl-4" :class="!props.textLogGenerationEnabled ? 'opacity-50' : ''">
              <div v-if="props.textLogGenerationEnabled">
                <div v-if="!isTextLogsAuto" class="flex items-center gap-2">
                  <input type="number" :value="props.minTextLogs || 1" @input="updateTextLogMin(Number(($event.target as HTMLInputElement).value))" min="1" :max="props.maxTextLogs || 20" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-cyan-500/50 outline-none text-white font-mono" />
                  <span class="text-white/30 text-xs">-</span>
                  <input type="number" :value="props.maxTextLogs || 5" @input="updateTextLogMax(Number(($event.target as HTMLInputElement).value))" :min="props.minTextLogs || 1" max="20" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-cyan-500/50 outline-none text-white font-mono" />
                </div>
                <div v-else class="text-[10px] text-white/30 italic">Determined by AI</div>
              </div>
            </td>
          </tr>

          <!-- Awards -->
          <tr class="hover:bg-slate-800/30 transition-colors border-b border-white/10">
            <td class="py-2.5 text-center">
              <input
                type="checkbox"
                :checked="props.awardGenerationEnabled"
                @change="emit('update:awardGenerationEnabled', ($event.target as HTMLInputElement).checked)"
                class="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0 h-4 w-4 block mx-auto cursor-pointer"
              />
            </td>
            <td class="py-2.5 pl-2" :class="!props.awardGenerationEnabled ? 'opacity-50' : ''">
              <span class="text-xs font-bold uppercase tracking-widest text-white/90 block">Awards</span>
              <span class="text-[10px] text-white/40 block">Trophies & achievements</span>
            </td>
            <td class="py-2.5 text-center">
              <button
                v-if="props.awardGenerationEnabled"
                type="button"
                @click="toggleAuto('awards')"
                class="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider transition-all border cursor-pointer select-none"
                :class="isAwardsAuto ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
              >
                {{ isAwardsAuto ? 'Auto' : 'Man' }}
              </button>
            </td>
            <td class="py-2.5 pl-4" :class="!props.awardGenerationEnabled ? 'opacity-50' : ''">
              <div v-if="props.awardGenerationEnabled">
                <div v-if="!isAwardsAuto" class="flex items-center gap-2">
                  <input type="number" :value="props.minAwards || 3" @input="updateAwardMin(Number(($event.target as HTMLInputElement).value))" min="0" :max="props.maxAwards || 20" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-indigo-500/50 outline-none text-white font-mono" />
                  <span class="text-white/30 text-xs">-</span>
                  <input type="number" :value="props.maxAwards || 8" @input="updateAwardMax(Number(($event.target as HTMLInputElement).value))" :min="props.minAwards || 0" max="20" class="w-12 h-6 text-xs text-center bg-slate-950 border border-white/10 rounded focus:border-indigo-500/50 outline-none text-white font-mono" />
                </div>
                <div v-else class="text-[10px] text-white/30 italic">Determined by AI</div>
              </div>
            </td>
          </tr>

          <!-- Custom Event Scripts Engine -->
          <tr class="hover:bg-slate-800/30 transition-colors border-b border-indigo-500/10 cursor-pointer" :class="props.scriptsGenerationEnabled ? 'bg-indigo-500/5' : ''" @click="emit('update:scriptsGenerationEnabled', !props.scriptsGenerationEnabled)">
            <td class="py-3 text-center">
              <input
                type="checkbox"
                :checked="props.scriptsGenerationEnabled ?? false"
                @change.stop="emit('update:scriptsGenerationEnabled', ($event.target as HTMLInputElement).checked)"
                @click.stop
                class="rounded bg-slate-800 border-slate-700 text-indigo-500 focus:ring-0 h-4 w-4 block mx-auto cursor-pointer"
              />
            </td>
            <td class="py-3 pl-2" colspan="3">
              <div class="flex items-center gap-2">
                <span class="text-xs font-bold uppercase tracking-widest block" :class="props.scriptsGenerationEnabled ? 'text-indigo-300' : 'text-white/90'">Event Scripts Engine</span>
                <span v-if="props.scriptsGenerationEnabled" class="text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Active</span>
              </div>
              <span class="text-[10px] text-white/40 block mt-0.5">Generate Python trigger scripts for deterministic puzzles & traps</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Warning for large worlds -->
    <div v-if="!isScenesAuto && props.maxScenes && props.maxScenes > 15" class="flex gap-2 sm:gap-3 items-start p-3 rounded-xl bg-amber-500/5 border border-amber-500/10 text-[10px] text-amber-400 uppercase tracking-wider leading-relaxed">
      <AlertTriangle class="w-4 h-4 shrink-0 mt-0.5" />
      <span>Large worlds (&gt; 15 scenes) may feel sparse. Walkthrough steps, items, and NPCs do not automatically scale up due to AI model limits.</span>
    </div>
  </div>
</template>
