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
  <div class="space-y-8">
    <div class="flex items-center justify-between">
      <h3 class="text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Story Foundation</h3>
      <InfoPopoverButton
        title="Story Foundation"
        :text="CREATE_ADVENTURE_HELP_TEXTS.storyFoundation"
      />
    </div>

    <!-- Basic Info -->
    <div class="space-y-6">
      <div>
        <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em] mb-3">Adventure Title</label>
        <input
          :value="modelValue.title"
          @input="$emit('update:modelValue', { ...modelValue, title: (($event.target as HTMLInputElement).value || '').slice(0, 50) })"
          type="text"
          maxlength="50"
          placeholder="Enter a title..."
          class="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 text-white focus:border-aether-primary outline-none transition-all placeholder:text-white/10"
        />
        <p class="mt-2 text-[10px] text-white/35 uppercase tracking-widest text-right">{{ modelValue.title.length }}/50</p>
      </div>

      <div>
        <div class="flex items-center justify-between mb-3">
          <label class="block text-xxs font-black text-white/40 uppercase tracking-[0.2em]">Story Idea & Context</label>
          <button
            type="button"
            :disabled="isSuggestingStoryIdea || canSuggestStoryIdea === false"
            @click="$emit('suggest-story-idea')"
            class="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border border-cyan-400/20 bg-cyan-500/10 text-cyan-300 text-[10px] font-black uppercase tracking-widest transition-all hover:bg-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Sparkles :class="['w-3.5 h-3.5', isSuggestingStoryIdea ? 'animate-spin' : '']" />
            {{ isSuggestingStoryIdea ? 'Generating...' : 'Auto Generate' }}
          </button>
        </div>
        <textarea
          :value="modelValue.storyIdea"
          @input="$emit('update:modelValue', { ...modelValue, storyIdea: ($event.target as HTMLTextAreaElement).value })"
          rows="4"
          placeholder="The Weaver will use this to seed the world's history and current conflicts..."
          class="w-full bg-white/5 border border-white/10 rounded-2xl px-6 py-4 text-white resize-y min-h-[7rem] focus:border-aether-primary outline-none transition-all placeholder:text-white/10"
        ></textarea>
      </div>
    </div>

    <!-- Target Language -->
    <div class="p-6 bg-cyan-500/5 border border-cyan-500/10 rounded-2xl space-y-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center text-cyan-400">
          <Sparkles class="w-5 h-5" />
        </div>
        <span class="text-xs font-black text-white/80 uppercase tracking-widest">Target Generation Language</span>
      </div>
      <div class="grid grid-cols-1 gap-3">
        <select 
          :value="modelValue.language"
          @change="$emit('update:modelValue', { ...modelValue, language: ($event.target as HTMLSelectElement).value })"
          class="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:border-cyan-400 outline-none transition-all cursor-pointer appearance-none"
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
        <p class="text-xxs text-white/30 uppercase tracking-[0.1em]">The Weaver will generate all names, descriptions, and plot points in this language.</p>
      </div>
    </div>
  </div>
</template>
