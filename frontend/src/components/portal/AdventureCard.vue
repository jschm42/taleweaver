<script setup lang="ts">
const props = defineProps<{
  adv: any
  activeMenuId: string | null
}>()

const emit = defineEmits<{
  (e: 'play', gameId: string): void
  (e: 'toggleMenu', event: Event, adventureId: string): void
  (e: 'edit', adventureId: string): void
  (e: 'exportAdz', adventureId: string, title: string): void
  (e: 'exportAdv', adventureId: string, title: string): void
  (e: 'delete', adventure: any): void
}>()
</script>

<template>
  <div
    class="adventure-card flex flex-col group cursor-pointer relative rounded-xl"
    @click="emit('play', props.adv.game_id)"
  >
    <div class="relative aspect-[3/2] overflow-visible rounded-xl mb-6 bg-aether-surface/30 border border-white/5 flex items-center justify-center group-hover:bg-aether-surface/50 transition-all duration-500">
      <button
        @click.stop="emit('toggleMenu', $event, props.adv.adventure_id)"
        class="absolute top-3 right-3 z-30 w-8 h-8 flex items-center justify-center rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-white opacity-0 group-hover:opacity-100 transition-all hover:bg-black/60"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
        </svg>
      </button>

      <div
        v-if="props.activeMenuId === props.adv.adventure_id"
        class="absolute top-12 right-3 z-40 w-44 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-fade-in"
      >
        <button
          @click.stop="emit('edit', props.adv.adventure_id)"
          class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-slate-300 hover:bg-aether-primary/20 hover:text-aether-primary transition-colors flex items-center gap-3 border-b border-white/5"
        >
          <i class="ra ra-wrench text-sm"></i>
          Edit Blueprint
        </button>
        <button
          @click.stop="emit('play', props.adv.game_id)"
          class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-slate-300 hover:bg-emerald-500/20 hover:text-emerald-400 transition-colors flex items-center gap-3 border-b border-white/5"
        >
          <i class="ra ra-player text-sm"></i>
          Play Chronicle
        </button>
        <button
          @click.stop="emit('exportAdz', props.adv.adventure_id, props.adv.adventure_title)"
          class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-slate-300 hover:bg-cyan-500/20 hover:text-cyan-300 transition-colors flex items-center gap-3 border-b border-white/5"
        >
          <i class="ra ra-save text-sm"></i>
          Export ADZ
        </button>
        <button
          @click.stop="emit('exportAdv', props.adv.adventure_id, props.adv.adventure_title)"
          class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-slate-300 hover:bg-blue-500/20 hover:text-blue-300 transition-colors flex items-center gap-3 border-b border-white/5"
        >
          <i class="ra ra-scroll-unfurled text-sm"></i>
          Export ADV
        </button>
        <button
          @click.stop="emit('delete', props.adv)"
          class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-red-400 hover:bg-red-500/20 transition-colors flex items-center gap-3"
        >
          <i class="ra ra-burning-embers text-sm"></i>
          Delete Adventure
        </button>
      </div>

      <div class="absolute inset-0 overflow-hidden rounded-xl">
        <img
          v-if="props.adv.image_url"
          :src="props.adv.image_url"
          class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
          alt="Cover"
        />

        <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent"></div>
      </div>

      <div class="absolute top-4 left-4">
        <span class="px-3 py-1 bg-aether-secondary/20 backdrop-blur-md border border-white/10 rounded-full text-[9px] font-black uppercase tracking-widest text-aether-secondary">
          {{ props.adv.genre || 'No Tone' }}
        </span>
      </div>
    </div>

    <div class="px-2">
      <h3 class="text-2xl font-black text-white mb-2 font-display line-clamp-1 group-hover:text-aether-primary transition-colors">
        {{ props.adv.adventure_title }}
      </h3>
      <p class="text-slate-400 text-sm font-narrative mb-6 line-clamp-2 opacity-70">
        {{ props.adv.description }}
      </p>

      <div class="space-y-3">
        <div class="flex flex-col gap-0.5">
          <span class="text-[8px] font-black text-slate-500 uppercase tracking-[0.2em]">Location</span>
          <span class="text-[10px] font-bold text-white truncate">{{ props.adv.current_scene_name || 'The Unknown' }}</span>
        </div>

        <div v-if="props.adv.quest_count > 0" class="space-y-2">
          <div class="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
            <span class="text-slate-500">Progress</span>
            <span class="text-aether-primary">
              {{ props.adv.completed_quest_count || 0 }} / {{ props.adv.quest_count }} Quests
              ({{ props.adv.progress }}%)
            </span>
          </div>
          <div class="h-1 bg-white/5 rounded-full overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-aether-primary/40 to-aether-primary shadow-ambient-emerald transition-all duration-1000"
              :style="{ width: `${props.adv.progress}%` }"
            ></div>
          </div>
        </div>
        <div v-else class="text-[10px] font-black uppercase tracking-widest text-slate-600 flex items-center gap-2">
          <i class="ra ra-scroll text-[8px] opacity-40"></i>
          No Quests active
        </div>
      </div>
    </div>
  </div>
</template>
