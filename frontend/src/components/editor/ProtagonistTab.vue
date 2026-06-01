<script setup lang="ts">
const props = defineProps<{
  debugData: any
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  visualsCacheVersion: number
  ruleEnforcementMode: string
}>()

const emit = defineEmits<{
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
}>()

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return `${imagePath}?v=${props.visualsCacheVersion}`
}
</script>

<template>
  <div class="space-y-8 animate-page-in">
    <section v-if="debugData?.protagonist" class="space-y-4 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">The Protagonist</h3>
        <button
          @click="emit('open-text-edit', 'protagonist', debugData.protagonist.id, debugData.protagonist.name, debugData.protagonist.description, '', debugData.protagonist.hp, debugData.protagonist.stamina, debugData.protagonist.mana, debugData.protagonist.goal, debugData.protagonist.character)"
          class="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-blue-500/20 border border-white/5 hover:border-blue-500/30 text-xs font-bold text-blue-400 hover:text-blue-300 uppercase tracking-widest transition-all"
        >
          <i class="ra ra-quill-pen"></i>
          Edit Character
        </button>
      </div>

      <div class="bg-black/20 border border-white/5 rounded-3xl p-6 flex flex-col md:flex-row gap-6 backdrop-blur-md shadow-inner">
        <div class="shrink-0 relative group">
          <div class="w-full md:w-56 h-72 md:h-80 rounded-2xl overflow-hidden bg-slate-800 border border-white/10 shadow-lg relative">
            <img
              v-if="debugData.protagonist.profile_image"
              :src="buildVisualImageUrl(debugData.protagonist.profile_image)"
              class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
            />
            <div v-else class="absolute inset-0 flex items-center justify-center text-slate-600">
              <i class="ra ra-person text-4xl"></i>
            </div>
            <div v-if="isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="absolute inset-0 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center z-10">
              <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
            </div>
          </div>
          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', debugData.protagonist.id, $event)" class="w-6 h-6 rounded-full bg-black/70 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg">
              <div class="flex flex-col gap-[3px]">
                <div class="w-[3px] h-[3px] bg-white rounded-full"></div>
                <div class="w-[3px] h-[3px] bg-white rounded-full"></div>
                <div class="w-[3px] h-[3px] bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === debugData.protagonist.id" class="absolute right-0 mt-1.5 w-52 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'protagonist', debugData.protagonist.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate Portrait</button>
              <button @click="emit('open-regen-dialog', 'protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
              <button @click="emit('open-upload-picker', 'protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Portrait</button>
              <button v-if="debugData.protagonist.profile_image" @click="emit('download-asset', debugData.protagonist.profile_image, `${debugData.protagonist.name || 'protagonist'}_portrait`)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Portrait</button>
            </div>
          </div>
        </div>

        <div class="flex-1 min-w-0 space-y-4">
          <div>
            <h4 class="text-xl font-black text-white tracking-tight">{{ debugData.protagonist.name }}</h4>
            <p class="text-xs font-bold text-emerald-400/70 uppercase tracking-widest mt-0.5">{{ debugData.protagonist.role || 'Protagonist' }}</p>
          </div>

          <div v-if="ruleEnforcementMode !== 'chat'" class="flex gap-3 flex-wrap">
            <div class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-red-500/10 border border-red-500/20 text-xs font-bold text-red-400">
              <i class="ra ra-heart text-[11px]"></i> {{ debugData.protagonist.hp ?? '-' }} HP
            </div>
            <div class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-400">
              <i class="ra ra-muscle-up text-[11px]"></i> {{ debugData.protagonist.stamina ?? '-' }} STM
            </div>
            <div v-if="ruleEnforcementMode === 'rpg'" class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs font-bold text-blue-400">
              <i class="ra ra-crystal-ball text-[11px]"></i> {{ debugData.protagonist.mana ?? '-' }} MAN
            </div>
          </div>

          <div class="grid grid-cols-1 gap-3">
            <div v-if="debugData.protagonist.description" class="space-y-1">
              <span class="text-[10px] font-black text-slate-600 uppercase tracking-widest">Bio</span>
              <p class="text-xs text-slate-400 leading-relaxed">{{ debugData.protagonist.description }}</p>
            </div>
            <div v-if="debugData.protagonist.goal || debugData.protagonist.character" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div v-if="debugData.protagonist.goal" class="space-y-1">
                <span class="text-[10px] font-black text-slate-600 uppercase tracking-widest">Motivation</span>
                <p class="text-xs text-slate-400 leading-relaxed">{{ debugData.protagonist.goal }}</p>
              </div>
              <div v-if="debugData.protagonist.character" class="space-y-1">
                <span class="text-[10px] font-black text-slate-600 uppercase tracking-widest">Traits</span>
                <p class="text-xs text-slate-400 leading-relaxed">{{ debugData.protagonist.character }}</p>
              </div>
            </div>
            <p v-if="!debugData.protagonist.description && !debugData.protagonist.goal && !debugData.protagonist.character" class="text-xs italic text-slate-600">No character details yet. Click "Edit Character" to add them.</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
