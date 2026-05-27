<script setup lang="ts">
defineProps<{
  form: any
}>()

const emit = defineEmits<{
  (e: 'save-changes'): void
  (e: 'update:generator', val: boolean): void
  (e: 'update:dynamic-items', val: boolean): void
  (e: 'update:can-damage-npcs', val: boolean): void
  (e: 'update:npcs-can-damage-protagonist', val: boolean): void
  (e: 'show-debug'): void
}>()
</script>

<template>
  <div class="space-y-10 animate-page-in">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <!-- Meta-Adventure Features -->
      <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6">
        <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
          <i class="ra ra-gear text-amber-500"></i> Special Features
        </h4>
        <p class="text-xs text-slate-400 leading-relaxed">Enable specialized behaviors for this adventure.</p>
        
        <div class="space-y-4">
          <div class="flex items-start gap-4 p-4 bg-white/5 border border-white/5 rounded-2xl group hover:border-emerald-500/30 transition-all">
            <div class="space-y-1 min-w-0 flex-1">
              <span class="text-xs font-black uppercase tracking-widest text-slate-200">Adventure Generator</span>
              <p class="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Enable Game-Designer NPC & Tools</p>
            </div>
            <button 
              @click="emit('update:generator', !form.is_adventure_generator)"
              :class="['w-14 h-8 shrink-0 mt-0.5 rounded-full transition-all relative flex items-center px-1', form.is_adventure_generator ? 'bg-emerald-600' : 'bg-slate-800']"
            >
              <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', form.is_adventure_generator ? 'translate-x-6' : 'translate-x-0']"></div>
            </button>
          </div>
        </div>
      </div>

      <!-- Data Debug -->
      <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6 md:col-span-2">
        <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
          <i class="ra ra-crystal-ball text-cyan-500"></i> Adventure Data Debug
        </h4>
        <p class="text-xs text-slate-400 leading-relaxed">View raw JSON data structures of this adventure template. Useful for deep analysis.</p>
        <div class="grid grid-cols-1 gap-3">
          <button @click="emit('show-debug')" class="flex items-center justify-between px-6 py-4 bg-white/5 hover:bg-cyan-500/10 border border-white/5 hover:border-cyan-500/30 rounded-2xl transition-all group">
            <span class="text-xs font-black uppercase tracking-widest text-slate-300 group-hover:text-cyan-400">Open JSON Debug Inspector</span>
            <i class="ra ra-search text-cyan-500"></i>
          </button>
        </div>
      </div>

      <!-- GM Capabilities -->
      <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6">
        <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
          <i class="ra ra-crystal-wand text-violet-400"></i> Game Master Capabilities
        </h4>
        <p class="text-xs text-slate-400 leading-relaxed">Control what the GM is allowed to do during live sessions of this adventure.</p>

        <!-- allow_dynamic_items toggle -->
        <div class="flex items-start gap-4 p-5 bg-black/30 rounded-2xl border border-white/5">
          <div class="space-y-1 min-w-0 flex-1">
            <p class="text-sm font-bold text-white">GM may create new items in-game</p>
            <p class="text-xs text-slate-500 leading-relaxed">Allows the GM to invent and drop new items (e.g. potions, loot) that were not in the original world manifest.</p>
          </div>
          <button
            id="toggle-allow-dynamic-items"
            type="button"
            @click="emit('update:dynamic-items', !form.allow_dynamic_items)"
            :class="[
              'w-14 h-8 shrink-0 mt-0.5 rounded-full transition-all relative flex items-center px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500',
              form.allow_dynamic_items ? 'bg-violet-600' : 'bg-slate-800'
            ]"
            :aria-pressed="form.allow_dynamic_items"
          >
            <div
              :class="[
                'w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300',
                form.allow_dynamic_items ? 'translate-x-6' : 'translate-x-0'
              ]"
            />
          </button>
        </div>

        <div class="flex items-start gap-4 p-5 bg-black/30 rounded-2xl border border-white/5">
          <div class="space-y-1 min-w-0 flex-1">
            <p class="text-sm font-bold text-white">Protagonist can damage NPCs</p>
            <p class="text-xs text-slate-500 leading-relaxed">Disabling this prevents all player attacks from reducing NPC HP.</p>
          </div>
          <button
            type="button"
            @click="emit('update:can-damage-npcs', !form.can_damage_npcs)"
            :class="[
              'w-14 h-8 shrink-0 mt-0.5 rounded-full transition-all relative flex items-center px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500',
              form.can_damage_npcs ? 'bg-rose-600' : 'bg-slate-800'
            ]"
            :aria-pressed="form.can_damage_npcs"
          >
            <div
              :class="[
                'w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300',
                form.can_damage_npcs ? 'translate-x-6' : 'translate-x-0'
              ]"
            />
          </button>
        </div>

        <div class="flex items-start gap-4 p-5 bg-black/30 rounded-2xl border border-white/5">
          <div class="space-y-1 min-w-0 flex-1">
            <p class="text-sm font-bold text-white">NPCs can damage protagonist</p>
            <p class="text-xs text-slate-500 leading-relaxed">Disabling this keeps enemy turns but prevents HP loss for the protagonist.</p>
          </div>
          <button
            type="button"
            @click="emit('update:npcs-can-damage-protagonist', !form.npcs_can_damage_protagonist)"
            :class="[
              'w-14 h-8 shrink-0 mt-0.5 rounded-full transition-all relative flex items-center px-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500',
              form.npcs_can_damage_protagonist ? 'bg-rose-600' : 'bg-slate-800'
            ]"
            :aria-pressed="form.npcs_can_damage_protagonist"
          >
            <div
              :class="[
                'w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300',
                form.npcs_can_damage_protagonist ? 'translate-x-6' : 'translate-x-0'
              ]"
            />
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
