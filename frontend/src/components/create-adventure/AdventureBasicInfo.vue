<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { CREATE_ADVENTURE_HELP_TEXTS } from '@/constants/createAdventureHelpTexts'

defineProps<{
  modelValue: {
    title: string
    storyIdea: string
    language: string
  }
  isSuggestingStoryIdea?: boolean
  canSuggestStoryIdea?: boolean
}>()

defineEmits<{
  (e: 'update:modelValue', value: any): void
  (e: 'suggest-story-idea'): void
}>()
</script>

<template>
  <div class="space-y-4 sm:space-y-5">
    <div class="flex items-center justify-between gap-2">
      <h3 class="text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Story Foundation</h3>
      <InfoPopoverButton
        title="Story Foundation"
        :text="CREATE_ADVENTURE_HELP_TEXTS.storyFoundation"
      />
    </div>

    <!-- Basic Info -->
    <div class="space-y-3.5 sm:space-y-4">
      <div>
        <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em] mb-1.5 sm:mb-2">Adventure Title</label>
        <input
          :value="modelValue.title"
          @input="$emit('update:modelValue', { ...modelValue, title: (($event.target as HTMLInputElement).value || '').slice(0, 50) })"
          type="text"
          maxlength="50"
          placeholder="Enter a title..."
          class="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm text-white focus:border-cyan-400 outline-none transition-all placeholder:text-white/20"
        />
        <p class="mt-1 text-[10px] text-white/35 uppercase tracking-widest text-right">{{ modelValue.title.length }}/50</p>
      </div>

      <div>
        <div class="flex items-center justify-between gap-2 mb-1.5 sm:mb-2">
          <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Story Idea & Context</label>
          <button
            type="button"
            :disabled="isSuggestingStoryIdea || canSuggestStoryIdea === false"
            @click="$emit('suggest-story-idea')"
            class="inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-300 text-[9px] sm:text-[10px] font-black uppercase tracking-widest transition-all hover:bg-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap active:scale-95"
          >
            <Sparkles :class="['w-3 h-3', isSuggestingStoryIdea ? 'animate-spin' : '']" />
            {{ isSuggestingStoryIdea ? 'Generating...' : 'Auto Generate' }}
          </button>
        </div>
        <textarea
          :value="modelValue.storyIdea"
          @input="$emit('update:modelValue', { ...modelValue, storyIdea: ($event.target as HTMLTextAreaElement).value })"
          rows="3"
          placeholder="The Weaver will use this to seed the world's history and current conflicts..."
          class="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm text-white resize-y min-h-[4.5rem] sm:min-h-[5.5rem] focus:border-cyan-400 outline-none transition-all placeholder:text-white/20"
        ></textarea>
      </div>
    </div>

    <!-- Target Language -->
    <div class="p-3 sm:p-3.5 bg-cyan-500/5 border border-cyan-500/10 rounded-xl space-y-2 sm:space-y-2.5">
      <div class="flex items-center gap-2.5">
        <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center text-cyan-400 shrink-0">
          <Sparkles class="w-3.5 h-3.5 sm:w-4 sm:h-4" />
        </div>
        <span class="text-xs font-black text-white/80 uppercase tracking-wider">Target Generation Language</span>
      </div>
      <div class="grid grid-cols-1 gap-1.5 sm:gap-2">
        <select
          :value="modelValue.language"
          @change="$emit('update:modelValue', { ...modelValue, language: ($event.target as HTMLSelectElement).value })"
          class="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs sm:text-sm text-white focus:border-cyan-400 outline-none transition-all cursor-pointer appearance-none"
        >
          <option value="">Default (English)</option>
          <option value="German">Deutsch</option>
          <option value="English">English</option>
          <option value="French">Français</option>
          <option value="Spanish">Español</option>
          <option value="Italian">Italiano</option>
          <option value="Japanese">Japanese</option>
          <option value="Chinese">Chinese</option>
          <option value="Russian">Russian</option>
          <option value="Portuguese">Portuguese</option>
        </select>
        <p class="text-[10px] text-white/30 uppercase tracking-[0.08em]">The Weaver will generate all names, descriptions, and plot points in this language.</p>
      </div>
    </div>
  </div>
</template>
