<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, MapPin, Trophy } from 'lucide-vue-next'

type RuleMode = 'rpg' | 'story' | 'chat'

const props = defineProps<{
  modelValue: {
    rule_enforcement_mode: RuleMode
    clock_enabled: boolean
    pacing_minutes: number
    min_scenes: number
    max_scenes: number
    award_generation_enabled: boolean
    min_awards: number
    max_awards: number
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
      <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Rule Enforcement Mode</label>
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
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center text-blue-400">
          <MapPin class="w-5 h-5" />
        </div>
        <span class="text-xs font-black text-white/80 uppercase tracking-widest">World Complexity (Scenes)</span>
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

    <!-- Awards Section -->
    <div class="p-6 bg-indigo-500/5 border border-indigo-500/10 rounded-2xl space-y-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Trophy class="w-5 h-5" />
          </div>
          <span class="text-xs font-black text-white/80 uppercase tracking-widest">Awards Weaver</span>
        </div>
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
  </div>
</template>
