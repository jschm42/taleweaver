<script setup lang="ts">
import type { AdventureTemplateSummary } from '@/types'

const props = defineProps<{
  template: AdventureTemplateSummary
}>()

const emit = defineEmits<{
  (e: 'startSession', templateId: string): void
  (e: 'edit', templateId: string): void
  (e: 'exportAdz', templateId: string, title: string): void
  (e: 'exportAdv', templateId: string, title: string): void
  (e: 'delete', templateId: string, title: string): void
}>()
</script>

<template>
  <article class="rounded-xl border border-white/10 bg-aether-surface/20 p-4 flex flex-col gap-4">
    <div class="aspect-[3/2] rounded-lg overflow-hidden bg-black/30 border border-white/5">
      <img
        v-if="props.template.image_url"
        :src="props.template.image_url"
        class="w-full h-full object-cover"
        alt="Adventure cover"
      />
      <div v-else class="w-full h-full flex items-center justify-center text-slate-500 text-xs uppercase tracking-widest">
        No Cover
      </div>
    </div>

    <div class="space-y-1">
      <h3 class="text-xl font-black text-white line-clamp-1">{{ props.template.title }}</h3>
      <p class="text-[11px] uppercase tracking-widest text-slate-400">
        {{ props.template.is_ready ? 'Template Ready' : (props.template.creation_status || 'Preparing template') }}
      </p>
      <p class="text-[11px] text-slate-400">
        Quests: {{ props.template.completed_quest_count || 0 }} / {{ props.template.quest_count || 0 }}
      </p>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <button
        class="px-3 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs font-bold uppercase tracking-widest hover:bg-emerald-500/30 transition-colors"
        @click="emit('startSession', props.template.template_id)"
      >
        Start Session
      </button>
      <button
        class="px-3 py-2 rounded-lg bg-white/10 text-slate-200 text-xs font-bold uppercase tracking-widest hover:bg-white/20 transition-colors"
        @click="emit('edit', props.template.template_id)"
      >
        Edit
      </button>
      <button
        class="px-3 py-2 rounded-lg bg-cyan-500/15 text-cyan-200 text-xs font-bold uppercase tracking-widest hover:bg-cyan-500/25 transition-colors"
        @click="emit('exportAdz', props.template.template_id, props.template.title)"
      >
        Export ADZ
      </button>
      <button
        class="px-3 py-2 rounded-lg bg-blue-500/15 text-blue-200 text-xs font-bold uppercase tracking-widest hover:bg-blue-500/25 transition-colors"
        @click="emit('exportAdv', props.template.template_id, props.template.title)"
      >
        Export ADV
      </button>
      <button
        class="col-span-2 px-3 py-2 rounded-lg bg-red-500/15 text-red-300 text-xs font-bold uppercase tracking-widest hover:bg-red-500/25 transition-colors"
        @click="emit('delete', props.template.template_id, props.template.title)"
      >
        Delete Template
      </button>
    </div>
  </article>
</template>
