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
    min_scenes: number
    max_scenes: number
    quest_generation_enabled: boolean
    min_quests: number
    max_quests: number
    container_generation_enabled: boolean
    max_containers: number
    text_log_generation_enabled: boolean
    max_text_logs: number
    award_generation_enabled: boolean
    min_awards: number
    max_awards: number
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

    <!-- Scene Generation Settings -->
    <div class="p-6 bg-blue-500/5 border border-blue-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400">
            <MapPin class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">World Complexity (Scenes)</span>
        </div>
        <InfoPopoverButton title="World Complexity" :text="CREATE_ADVENTURE_HELP_TEXTS.sceneComplexity" />
      </div>

      <div class="grid grid-cols-2 gap-8">
        <div class="space-y-3">
          <div class="flex justify-between">
            <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min</label>
            <span class="text-xs font-mono text-blue-400">{{ modelValue.min_scenes }}</span>
          </div>
          <input 
            type="range" 
            :value="modelValue.min_scenes"
            @input="update('min_scenes', Number(($event.target as HTMLInputElement).value))"
            min="1" :max="modelValue.max_scenes" class="w-full accent-blue-500" 
          />
        </div>
        <div class="space-y-3">
          <div class="flex justify-between">
            <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max</label>
            <span class="text-xs font-mono text-blue-400">{{ modelValue.max_scenes }}</span>
          </div>
          <input 
            type="range" 
            :value="modelValue.max_scenes"
            @input="update('max_scenes', Number(($event.target as HTMLInputElement).value))"
            :min="modelValue.min_scenes" max="20" class="w-full accent-blue-500" 
          />
        </div>
      </div>
    </div>

    <!-- Quest Generation -->
    <div class="p-6 bg-violet-500/5 border border-violet-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-violet-500/20 flex items-center justify-center text-violet-400">
            <MapPin class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">Quest Generation</span>
        </div>
        <InfoPopoverButton title="Quest Generation" :text="CREATE_ADVENTURE_HELP_TEXTS.questGeneration" />
        <div
          @click="update('quest_generation_enabled', !modelValue.quest_generation_enabled)"
          :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.quest_generation_enabled ? 'bg-violet-500' : 'bg-slate-700']"
        >
          <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.quest_generation_enabled ? 'left-6' : 'left-1']"></div>
        </div>
      </div>

      <div v-if="modelValue.quest_generation_enabled" class="grid grid-cols-2 gap-8">
        <div class="space-y-3">
          <div class="flex justify-between">
            <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min</label>
            <span class="text-xs font-mono text-violet-300">{{ modelValue.min_quests }}</span>
          </div>
          <input
            type="range"
            :value="modelValue.min_quests"
            @input="update('min_quests', Number(($event.target as HTMLInputElement).value))"
            min="1"
            :max="modelValue.max_quests"
            class="w-full accent-violet-500"
          />
        </div>
        <div class="space-y-3">
          <div class="flex justify-between">
            <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max</label>
            <span class="text-xs font-mono text-violet-300">{{ modelValue.max_quests }}</span>
          </div>
          <input
            type="range"
            :value="modelValue.max_quests"
            @input="update('max_quests', Number(($event.target as HTMLInputElement).value))"
            :min="modelValue.min_quests"
            max="20"
            class="w-full accent-violet-500"
          />
        </div>
      </div>
    </div>

    <!-- Container Generation -->
    <div class="p-6 bg-amber-500/5 border border-amber-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-400">
            <Box class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">Container Generation</span>
        </div>
        <InfoPopoverButton title="Container Generation" :text="CREATE_ADVENTURE_HELP_TEXTS.containerGeneration" />
        <div
          @click="update('container_generation_enabled', !modelValue.container_generation_enabled)"
          :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.container_generation_enabled ? 'bg-amber-500' : 'bg-slate-700']"
        >
          <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.container_generation_enabled ? 'left-6' : 'left-1']"></div>
        </div>
      </div>

      <div v-if="modelValue.container_generation_enabled" class="space-y-3">
        <div class="flex justify-between items-center">
          <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Containers</label>
          <span class="text-xs font-mono text-amber-300">{{ modelValue.max_containers }}</span>
        </div>
        <input
          type="range"
          :value="modelValue.max_containers"
          @input="update('max_containers', Number(($event.target as HTMLInputElement).value))"
          min="0"
          max="30"
          class="w-full accent-amber-500"
        />
      </div>
    </div>

    <!-- Text Log Generation -->
    <div class="p-6 bg-cyan-500/5 border border-cyan-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center text-cyan-400">
            <MapPin class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">Text Log Generation</span>
        </div>
        <InfoPopoverButton title="Text Log Generation" :text="CREATE_ADVENTURE_HELP_TEXTS.textLogGeneration" />
        <div
          @click="update('text_log_generation_enabled', !modelValue.text_log_generation_enabled)"
          :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.text_log_generation_enabled ? 'bg-cyan-500' : 'bg-slate-700']"
        >
          <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.text_log_generation_enabled ? 'left-6' : 'left-1']"></div>
        </div>
      </div>

      <div v-if="modelValue.text_log_generation_enabled" class="space-y-3">
        <div class="flex justify-between items-center">
          <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max Text Logs</label>
          <span class="text-xs font-mono text-cyan-300">{{ modelValue.max_text_logs }}</span>
        </div>
        <input
          type="range"
          :value="modelValue.max_text_logs"
          @input="update('max_text_logs', Number(($event.target as HTMLInputElement).value))"
          min="0"
          max="30"
          class="w-full accent-cyan-500"
        />
      </div>
    </div>

    <!-- Awards Section -->
    <div class="p-6 bg-indigo-500/5 border border-indigo-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Trophy class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">Awards Weaver</span>
        </div>
        <InfoPopoverButton title="Awards Weaver" :text="CREATE_ADVENTURE_HELP_TEXTS.awards" />
        <div 
          @click="update('award_generation_enabled', !modelValue.award_generation_enabled)"
          :class="['w-10 h-5 rounded-full relative cursor-pointer transition-colors', modelValue.award_generation_enabled ? 'bg-indigo-500' : 'bg-slate-700']"
        >
          <div :class="['absolute top-1 w-3 h-3 bg-white rounded-full transition-all shadow-sm', modelValue.award_generation_enabled ? 'left-6' : 'left-1']"></div>
        </div>
      </div>

      <div v-if="modelValue.award_generation_enabled" class="grid grid-cols-2 gap-8">
        <div class="space-y-3">
          <div class="flex justify-between">
            <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Min</label>
            <span class="text-xs font-mono text-indigo-400">{{ modelValue.min_awards }}</span>
          </div>
          <input 
            type="range" 
            :value="modelValue.min_awards"
            @input="update('min_awards', Number(($event.target as HTMLInputElement).value))"
            min="1" :max="modelValue.max_awards" class="w-full accent-indigo-500" 
          />
        </div>
        <div class="space-y-3">
          <div class="flex justify-between">
            <label class="text-xxs font-black text-white/40 uppercase tracking-widest">Max</label>
            <span class="text-xs font-mono text-indigo-400">{{ modelValue.max_awards }}</span>
          </div>
          <input 
            type="range" 
            :value="modelValue.max_awards"
            @input="update('max_awards', Number(($event.target as HTMLInputElement).value))"
            :min="modelValue.min_awards" max="20" class="w-full accent-indigo-500" 
          />
        </div>
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
