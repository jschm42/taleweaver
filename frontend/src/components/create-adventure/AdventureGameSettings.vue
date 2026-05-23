<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, Box, MapPin, Trophy } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

type RuleMode = 'rpg' | 'story' | 'chat'

const props = defineProps<{
  modelValue: {
    rule_enforcement_mode: RuleMode
    clock_enabled: boolean
    pacing_minutes: number
    min_scenes: number | null
    max_scenes: number | null
    min_items: number | null
    max_items: number | null
    quest_generation_enabled: boolean
    min_quests: number | null
    max_quests: number | null
    container_generation_enabled: boolean
    min_containers: number | null
    max_containers: number | null
    text_log_generation_enabled: boolean
    min_text_logs: number | null
    max_text_logs: number | null
    award_generation_enabled: boolean
    min_awards: number | null
    max_awards: number | null
    can_damage_npcs: boolean
    npcs_can_damage_protagonist: boolean
  }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: any): void
}>()

const ruleModeHelp = computed(() => {
  if (props.modelValue.rule_enforcement_mode === 'rpg') {
    return 'The Game Master enforces strict rules and mechanics. Best for a challenging RPG experience.'
  }
  if (props.modelValue.rule_enforcement_mode === 'story') {
    return 'Story and atmosphere foreground. RPG elements optional.'
  }
  return 'Story, atmosphere, chatting with NPCs. No strict rules check.'
})

const isScenesAuto = computed(() => props.modelValue.min_scenes === null && props.modelValue.max_scenes === null)
const isItemsAuto = computed(() => props.modelValue.min_items === null && props.modelValue.max_items === null)
const isContainersAuto = computed(() => props.modelValue.min_containers === null && props.modelValue.max_containers === null)
const isTextLogsAuto = computed(() => props.modelValue.min_text_logs === null && props.modelValue.max_text_logs === null)
const isQuestsAuto = computed(() => props.modelValue.min_quests === null && props.modelValue.max_quests === null)
const isAwardsAuto = computed(() => props.modelValue.min_awards === null && props.modelValue.max_awards === null)

function toggleAuto(type: 'scenes' | 'items' | 'containers' | 'textLogs' | 'quests' | 'awards') {
  if (type === 'scenes') {
    if (isScenesAuto.value) {
      update('min_scenes', 3)
      update('max_scenes', 6)
    } else {
      update('min_scenes', null)
      update('max_scenes', null)
    }
  } else if (type === 'items') {
    if (isItemsAuto.value) {
      update('min_items', 5)
      update('max_items', 25)
    } else {
      update('min_items', null)
      update('max_items', null)
    }
  } else if (type === 'containers') {
    if (isContainersAuto.value) {
      update('min_containers', 2)
      update('max_containers', 6)
    } else {
      update('min_containers', null)
      update('max_containers', null)
    }
  } else if (type === 'textLogs') {
    if (isTextLogsAuto.value) {
      update('min_text_logs', 1)
      update('max_text_logs', 5)
    } else {
      update('min_text_logs', null)
      update('max_text_logs', null)
    }
  } else if (type === 'quests') {
    if (isQuestsAuto.value) {
      update('min_quests', 3)
      update('max_quests', 5)
    } else {
      update('min_quests', null)
      update('max_quests', null)
    }
  } else if (type === 'awards') {
    if (isAwardsAuto.value) {
      update('min_awards', 3)
      update('max_awards', 8)
    } else {
      update('min_awards', null)
      update('max_awards', null)
    }
  }
}

function updateSceneMin(val: number) {
  update('min_scenes', val)
  if (props.modelValue.max_scenes !== null && val > props.modelValue.max_scenes) {
    update('max_scenes', val)
  }
}
function updateSceneMax(val: number) {
  update('max_scenes', val)
  if (props.modelValue.min_scenes !== null && val < props.modelValue.min_scenes) {
    update('min_scenes', val)
  }
}

function updateItemMin(val: number) {
  update('min_items', val)
  if (props.modelValue.max_items !== null && val > props.modelValue.max_items) {
    update('max_items', val)
  }
}
function updateItemMax(val: number) {
  update('max_items', val)
  if (props.modelValue.min_items !== null && val < props.modelValue.min_items) {
    update('min_items', val)
  }
}

function updateContainerMin(val: number) {
  update('min_containers', val)
  if (props.modelValue.max_containers !== null && val > props.modelValue.max_containers) {
    update('max_containers', val)
  }
}
function updateContainerMax(val: number) {
  update('max_containers', val)
  if (props.modelValue.min_containers !== null && val < props.modelValue.min_containers) {
    update('min_containers', val)
  }
}

function updateTextLogMin(val: number) {
  update('min_text_logs', val)
  if (props.modelValue.max_text_logs !== null && val > props.modelValue.max_text_logs) {
    update('max_text_logs', val)
  }
}
function updateTextLogMax(val: number) {
  update('max_text_logs', val)
  if (props.modelValue.min_text_logs !== null && val < props.modelValue.min_text_logs) {
    update('min_text_logs', val)
  }
}

function updateQuestMin(val: number) {
  update('min_quests', val)
  if (props.modelValue.max_quests !== null && val > props.modelValue.max_quests) {
    update('max_quests', val)
  }
}
function updateQuestMax(val: number) {
  update('max_quests', val)
  if (props.modelValue.min_quests !== null && val < props.modelValue.min_quests) {
    update('min_quests', val)
  }
}

function updateAwardMin(val: number) {
  update('min_awards', val)
  if (props.modelValue.max_awards !== null && val > props.modelValue.max_awards) {
    update('max_awards', val)
  }
}
function updateAwardMax(val: number) {
  update('max_awards', val)
  if (props.modelValue.min_awards !== null && val < props.modelValue.min_awards) {
    update('min_awards', val)
  }
}

function update(field: string, value: any) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <div class="space-y-8">
    <!-- Rule Enforcement -->
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Rule Enforcement Mode</label>
        <InfoPopoverButton title="Rule Enforcement" :text="CREATE_ADVENTURE_HELP_TEXTS.ruleEnforcement" />
      </div>
      <div class="grid grid-cols-3 gap-3">
        <button
          v-for="mode in (['rpg', 'story', 'chat'] as RuleMode[])"
          :key="mode"
          @click="update('rule_enforcement_mode', mode)"
          class="px-4 py-4 rounded-2xl border-2 transition-all flex flex-col items-center gap-1"
          :class="modelValue.rule_enforcement_mode === mode ? 'border-aether-primary bg-aether-primary/10 text-white' : 'border-white/5 bg-white/5 text-white/40 hover:border-white/10'"
        >
          <span class="text-xxs font-black uppercase tracking-widest">{{ mode === 'rpg' ? 'RPG' : mode }}</span>
        </button>
      </div>
      <p class="text-xxs text-white/30 uppercase tracking-widest text-center">{{ ruleModeHelp }}</p>
      
    </div>

    <!-- World Pacing & Time -->
    <div class="p-6 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-400">
            <MapPin class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">In-Game Pacing</span>
        </div>
        <InfoPopoverButton title="In-Game Pacing" :text="CREATE_ADVENTURE_HELP_TEXTS.pacing" />
        <div 
          @click="update('clock_enabled', !modelValue.clock_enabled)"
          :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.clock_enabled ? 'bg-emerald-500' : 'bg-slate-700']"
        >
          <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.clock_enabled ? 'left-6' : 'left-1']"></div>
        </div>
      </div>

      <div class="space-y-4" v-if="modelValue.clock_enabled">
        <div class="flex justify-between items-center">
          <span class="text-xxs font-black text-white/40 uppercase tracking-widest">Pacing (Min/Action)</span>
          <span class="text-xs font-mono text-emerald-400">{{ modelValue.pacing_minutes }}m</span>
        </div>
        <input 
          type="range" 
          :value="modelValue.pacing_minutes"
          @input="update('pacing_minutes', Number(($event.target as HTMLInputElement).value))"
          min="1" 
          max="30" 
          class="w-full accent-emerald-500 bg-white/5 h-1.5 rounded-lg appearance-none cursor-pointer"
        />
      </div>
    </div>

    <!-- Consolidated World Density & Constraints Panel -->
    <div class="p-6 bg-slate-900/80 border border-slate-700/50 rounded-2xl space-y-6 shadow-xl relative overflow-hidden">
      <!-- Glow effect behind -->
      <div class="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>
      
      <div class="flex items-center justify-between border-b border-white/10 pb-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400">
            <Box class="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <span class="text-sm font-black text-white uppercase tracking-wider block">World Density & Constraints</span>
            <span class="text-[10px] text-white/40 uppercase tracking-widest">Adjust complexity bounds or set to Auto</span>
          </div>
        </div>
        <InfoPopoverButton title="World Constraints" :text="CREATE_ADVENTURE_HELP_TEXTS.sceneComplexity" />
      </div>

      <div class="space-y-6">
        <!-- Scenes Row -->
        <div class="p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-blue-500/20">
          <div class="flex items-center justify-between">
            <div>
              <span class="text-xs font-black uppercase tracking-widest block" :class="isScenesAuto ? 'text-white/40' : 'text-white/80'">Scenes (Locations)</span>
              <span class="text-[10px] text-white/40 uppercase tracking-wider">Number of unique areas to explore</span>
            </div>
            <!-- Auto switch -->
            <button 
              type="button"
              @click="toggleAuto('scenes')"
              class="px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border"
              :class="isScenesAuto ? 'bg-blue-500/20 border-blue-500/40 text-blue-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
            >
              {{ isScenesAuto ? 'Auto Mode' : 'Manual' }}
            </button>
          </div>

          <div v-if="isScenesAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI will automatically determine optimal scene count based on your story idea.
          </div>
          <div v-else class="grid grid-cols-2 gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Scenes</label>
                <span class="text-xs font-mono text-blue-400">{{ modelValue.min_scenes }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.min_scenes || 3"
                @input="updateSceneMin(Number(($event.target as HTMLInputElement).value))"
                min="1" :max="modelValue.max_scenes || 50" class="w-full accent-blue-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Scenes</label>
                <span class="text-xs font-mono text-blue-400">{{ modelValue.max_scenes }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.max_scenes || 6"
                @input="updateSceneMax(Number(($event.target as HTMLInputElement).value))"
                :min="modelValue.min_scenes || 1" max="50" class="w-full accent-blue-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
          </div>
        </div>

        <!-- Items Row -->
        <div class="p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-lime-500/20">
          <div class="flex items-center justify-between">
            <div>
              <span class="text-xs font-black uppercase tracking-widest block" :class="isItemsAuto ? 'text-white/40' : 'text-white/80'">Items & Objects</span>
              <span class="text-[10px] text-white/40 uppercase tracking-wider">Loot, weapons, keys, and quest items</span>
            </div>
            <!-- Auto switch -->
            <button 
              type="button"
              @click="toggleAuto('items')"
              class="px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border"
              :class="isItemsAuto ? 'bg-lime-500/20 border-lime-500/40 text-lime-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
            >
              {{ isItemsAuto ? 'Auto Mode' : 'Manual' }}
            </button>
          </div>

          <div v-if="isItemsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI will generate items organically as needed for puzzles and exploration.
          </div>
          <div v-else class="grid grid-cols-2 gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Items</label>
                <span class="text-xs font-mono text-lime-400">{{ modelValue.min_items }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.min_items || 5"
                @input="updateItemMin(Number(($event.target as HTMLInputElement).value))"
                min="1" :max="modelValue.max_items || 100" class="w-full accent-lime-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Items</label>
                <span class="text-xs font-mono text-lime-400">{{ modelValue.max_items }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.max_items || 25"
                @input="updateItemMax(Number(($event.target as HTMLInputElement).value))"
                :min="modelValue.min_items || 1" max="100" class="w-full accent-lime-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
          </div>
        </div>

        <!-- Containers Row -->
        <div class="p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-amber-500/20">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div 
                @click="update('container_generation_enabled', !modelValue.container_generation_enabled)"
                :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.container_generation_enabled ? 'bg-amber-500' : 'bg-slate-700']"
              >
                <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.container_generation_enabled ? 'left-6' : 'left-1']"></div>
              </div>
              <div>
                <span class="text-xs font-black uppercase tracking-widest block" :class="modelValue.container_generation_enabled ? 'text-white/80' : 'text-white/30'">Chests & Containers</span>
                <span class="text-[10px] text-white/40 uppercase tracking-wider">Locked safes, dressers, lockboxes</span>
              </div>
            </div>
            <!-- Auto switch (only show if container generation enabled) -->
            <button 
              v-if="modelValue.container_generation_enabled"
              type="button"
              @click="toggleAuto('containers')"
              class="px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border"
              :class="isContainersAuto ? 'bg-amber-500/20 border-amber-500/40 text-amber-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
            >
              {{ isContainersAuto ? 'Auto Mode' : 'Manual' }}
            </button>
          </div>

          <div v-if="!modelValue.container_generation_enabled" class="text-xs text-white/30 italic uppercase tracking-wider py-2">
            🚫 Container generation is disabled. Items will not be inside chests or safes.
          </div>
          <div v-else-if="isContainersAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI determines optimal container placement to house items and puzzle clues.
          </div>
          <div v-else class="grid grid-cols-2 gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Containers</label>
                <span class="text-xs font-mono text-amber-400">{{ modelValue.min_containers }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.min_containers || 2"
                @input="updateContainerMin(Number(($event.target as HTMLInputElement).value))"
                min="0" :max="modelValue.max_containers || 30" class="w-full accent-amber-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Containers</label>
                <span class="text-xs font-mono text-amber-400">{{ modelValue.max_containers }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.max_containers || 6"
                @input="updateContainerMax(Number(($event.target as HTMLInputElement).value))"
                :min="modelValue.min_containers || 0" max="30" class="w-full accent-amber-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
          </div>
        </div>

        <!-- Text Logs Row -->
        <div class="p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-cyan-500/20">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div 
                @click="update('text_log_generation_enabled', !modelValue.text_log_generation_enabled)"
                :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.text_log_generation_enabled ? 'bg-cyan-500' : 'bg-slate-700']"
              >
                <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.text_log_generation_enabled ? 'left-6' : 'left-1']"></div>
              </div>
              <div>
                <span class="text-xs font-black uppercase tracking-widest block" :class="modelValue.text_log_generation_enabled ? 'text-white/80' : 'text-white/30'">Readable Text Logs</span>
                <span class="text-[10px] text-white/40 uppercase tracking-wider">Books, signs, letters, diaries</span>
              </div>
            </div>
            <!-- Auto switch (only show if text log generation enabled) -->
            <button 
              v-if="modelValue.text_log_generation_enabled"
              type="button"
              @click="toggleAuto('textLogs')"
              class="px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border"
              :class="isTextLogsAuto ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
            >
              {{ isTextLogsAuto ? 'Auto Mode' : 'Manual' }}
            </button>
          </div>

          <div v-if="!modelValue.text_log_generation_enabled" class="text-xs text-white/30 italic uppercase tracking-wider py-2">
            🚫 Text log generation is disabled. No readable scrolls, signing, or diaries.
          </div>
          <div v-else-if="isTextLogsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI creates immersive written documents, clues, or warnings contextually.
          </div>
          <div v-else class="grid grid-cols-2 gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Text Logs</label>
                <span class="text-xs font-mono text-cyan-400">{{ modelValue.min_text_logs }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.min_text_logs || 1"
                @input="updateTextLogMin(Number(($event.target as HTMLInputElement).value))"
                min="0" :max="modelValue.max_text_logs || 30" class="w-full accent-cyan-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Text Logs</label>
                <span class="text-xs font-mono text-cyan-400">{{ modelValue.max_text_logs }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.max_text_logs || 5"
                @input="updateTextLogMax(Number(($event.target as HTMLInputElement).value))"
                :min="modelValue.min_text_logs || 0" max="30" class="w-full accent-cyan-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
          </div>
        </div>

        <!-- Quests Row -->
        <div class="p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-violet-500/20">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div 
                @click="update('quest_generation_enabled', !modelValue.quest_generation_enabled)"
                :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.quest_generation_enabled ? 'bg-violet-500' : 'bg-slate-700']"
              >
                <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.quest_generation_enabled ? 'left-6' : 'left-1']"></div>
              </div>
              <div>
                <span class="text-xs font-black uppercase tracking-widest block" :class="modelValue.quest_generation_enabled ? 'text-white/80' : 'text-white/30'">Quests & Objectives</span>
                <span class="text-[10px] text-white/40 uppercase tracking-wider">Main and side quests dynamically generated</span>
              </div>
            </div>
            <!-- Auto switch (only show if quest generation enabled) -->
            <button 
              v-if="modelValue.quest_generation_enabled"
              type="button"
              @click="toggleAuto('quests')"
              class="px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border"
              :class="isQuestsAuto ? 'bg-violet-500/20 border-violet-500/40 text-violet-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
            >
              {{ isQuestsAuto ? 'Auto Mode' : 'Manual' }}
            </button>
          </div>

          <div v-if="!modelValue.quest_generation_enabled" class="text-xs text-white/30 italic uppercase tracking-wider py-2">
            🚫 Quest generation is disabled. No quest structure will be created.
          </div>
          <div v-else-if="isQuestsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI determines optimal quests dynamically based on target complexity and scenes.
          </div>
          <div v-else class="grid grid-cols-2 gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Quests</label>
                <span class="text-xs font-mono text-violet-300">{{ modelValue.min_quests }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.min_quests || 3"
                @input="updateQuestMin(Number(($event.target as HTMLInputElement).value))"
                min="0" :max="modelValue.max_quests || 30" class="w-full accent-violet-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Quests</label>
                <span class="text-xs font-mono text-violet-300">{{ modelValue.max_quests }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.max_quests || 5"
                @input="updateQuestMax(Number(($event.target as HTMLInputElement).value))"
                :min="modelValue.min_quests || 0" max="30" class="w-full accent-violet-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
          </div>
        </div>

        <!-- Awards Row -->
        <div class="p-4 rounded-xl bg-slate-950/40 border border-white/5 space-y-3 transition-all hover:border-indigo-500/20">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div 
                @click="update('award_generation_enabled', !modelValue.award_generation_enabled)"
                :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.award_generation_enabled ? 'bg-indigo-500' : 'bg-slate-700']"
              >
                <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.award_generation_enabled ? 'left-6' : 'left-1']"></div>
              </div>
              <div>
                <span class="text-xs font-black uppercase tracking-widest block" :class="modelValue.award_generation_enabled ? 'text-white/80' : 'text-white/30'">Awards & Milestones</span>
                <span class="text-[10px] text-white/40 uppercase tracking-wider">Achievements, trophies, and rewards</span>
              </div>
            </div>
            <!-- Auto switch (only show if award generation enabled) -->
            <button 
              v-if="modelValue.award_generation_enabled"
              type="button"
              @click="toggleAuto('awards')"
              class="px-3 py-1 rounded-full text-xxs font-black uppercase tracking-wider transition-all border"
              :class="isAwardsAuto ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-400' : 'bg-slate-800 border-white/10 text-white/40 hover:text-white'"
            >
              {{ isAwardsAuto ? 'Auto Mode' : 'Manual' }}
            </button>
          </div>

          <div v-if="!modelValue.award_generation_enabled" class="text-xs text-white/30 italic uppercase tracking-wider py-2">
            🚫 Award generation is disabled. No achievements will be created.
          </div>
          <div v-else-if="isAwardsAuto" class="text-xs text-white/40 italic uppercase tracking-wider py-2">
            ✨ AI determines optimal achievements and awards based on quest complexity.
          </div>
          <div v-else class="grid grid-cols-2 gap-6 pt-2">
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min Awards</label>
                <span class="text-xs font-mono text-indigo-400">{{ modelValue.min_awards }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.min_awards || 3"
                @input="updateAwardMin(Number(($event.target as HTMLInputElement).value))"
                min="0" :max="modelValue.max_awards || 20" class="w-full accent-indigo-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between">
                <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Awards</label>
                <span class="text-xs font-mono text-indigo-400">{{ modelValue.max_awards }}</span>
              </div>
              <input 
                type="range" 
                :value="modelValue.max_awards || 8"
                @input="updateAwardMax(Number(($event.target as HTMLInputElement).value))"
                :min="modelValue.min_awards || 0" max="20" class="w-full accent-indigo-500 bg-white/5 h-1 rounded-lg appearance-none cursor-pointer" 
              />
            </div>
          </div>
        </div>
      </div>
      
      <div v-if="!isScenesAuto && modelValue.max_scenes && modelValue.max_scenes > 15" class="flex gap-3 items-start p-3 rounded-xl bg-amber-500/5 border border-amber-500/10 text-[10px] text-amber-400 uppercase tracking-wider leading-relaxed">
        <AlertTriangle class="w-4 h-4 shrink-0" />
        <span>Large worlds (&gt; 15 scenes) may feel sparse. Walkthrough steps, items, and NPCs do not automatically scale up due to AI model limits.</span>
      </div>
    </div>

    <!-- Combat Permissions -->
    <div class="p-6 bg-rose-500/5 border border-rose-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center text-rose-400">
            <AlertTriangle class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">Combat Permissions</span>
        </div>
        <InfoPopoverButton title="Combat Permissions" :text="CREATE_ADVENTURE_HELP_TEXTS.combatPermissions" />
      </div>

      <div class="space-y-4">
        <div class="flex items-center justify-between p-3 rounded-xl border border-white/10 bg-black/20">
          <div class="space-y-1 pr-4">
            <p class="text-xs font-black text-white/80 uppercase tracking-widest">Protagonist Can Damage NPCs</p>
            <p class="text-[10px] text-white/40 uppercase tracking-wider">If disabled, no player attack can deal HP damage to NPCs.</p>
          </div>
          <div 
            @click="update('can_damage_npcs', !modelValue.can_damage_npcs)"
            :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.can_damage_npcs ? 'bg-rose-500' : 'bg-slate-700']"
          >
            <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.can_damage_npcs ? 'left-6' : 'left-1']"></div>
          </div>
        </div>

        <div class="flex items-center justify-between p-3 rounded-xl border border-white/10 bg-black/20">
          <div class="space-y-1 pr-4">
            <p class="text-xs font-black text-white/80 uppercase tracking-widest">NPCs Can Damage Protagonist</p>
            <p class="text-[10px] text-white/40 uppercase tracking-wider">If disabled, enemy turns still happen but cannot reduce player HP.</p>
          </div>
          <div 
            @click="update('npcs_can_damage_protagonist', !modelValue.npcs_can_damage_protagonist)"
            :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.npcs_can_damage_protagonist ? 'bg-rose-500' : 'bg-slate-700']"
          >
            <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.npcs_can_damage_protagonist ? 'left-6' : 'left-1']"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
