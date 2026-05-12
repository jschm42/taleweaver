<script setup lang="ts">
import { Save, X, AlertTriangle } from 'lucide-vue-next'
import { getItemIcon } from '@/utils/game_icons'
import type { VisualKind } from '@/utils/editor_utils'

const props = defineProps<{
  form: any
  adventure: any
  debugData: any
  imageStylesCatalog: any[]
  editingField: string | null
  tempValue: string
  isSaving: boolean
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  editorNpcs: any[]
  editorScenes: any[]
  editorObjects: any[]
  ruleEnforcementMode: string
}>()

const emit = defineEmits<{
  (e: 'start-edit', field: string, value: string): void
  (e: 'save-field'): void
  (e: 'cancel-edit'): void
  (e: 'save-changes'): void
  (e: 'quick-regen', kind: VisualKind, id: string): void
  (e: 'regen-all', kind: VisualKind): void
  (e: 'open-regen-dialog', kind: VisualKind, id: string, label: string): void
  (e: 'open-upload-picker', kind: VisualKind, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'handle-hover', entity: any, event: MouseEvent): void
  (e: 'clear-hover'): void
  (e: 'clear-creation-error'): void
  (e: 'update:pacing', val: number): void
  (e: 'update:style', val: string): void
  (e: 'update:tempValue', val: string): void
}>()

// Helper functions that don't need parent state
function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return imagePath // In a real scenario, this would use a versioned URL from props or a global util
}

function getCoverNarrativeContext() {
  if (!props.debugData) return ''
  return props.debugData.adventure?.plot || props.debugData.adventure?.original_prompt || ''
}

import bronzeTrophy from '@/assets/svg/bronze-award-trophy.svg'
import silverTrophy from '@/assets/svg/silver-award-trophy.svg'
import goldTrophy from '@/assets/svg/gold-award-trophy.svg'

function getAwardIcon(tier: string) {
  const t = (tier || '').toLowerCase()
  if (t === 'gold') return goldTrophy
  if (t === 'silver') return silverTrophy
  return bronzeTrophy
}

function handlePacingInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:pacing', parseInt(target.value))
}
</script>

<template>
  <div class="space-y-10 animate-page-in">
    <!-- Creation Error/Warning Banner -->
    <div v-if="adventure?.creation_error" class="bg-amber-500/10 border border-amber-500/20 rounded-3xl p-6 flex items-start gap-5 backdrop-blur-md shadow-lg shadow-amber-500/5 animate-page-in">
      <div class="w-12 h-12 rounded-2xl bg-amber-500/20 flex items-center justify-center text-amber-500 shrink-0 shadow-lg shadow-amber-500/10">
        <AlertTriangle class="w-6 h-6" />
      </div>
      <div class="flex-1 space-y-1">
        <h3 class="text-amber-500 font-black uppercase tracking-[0.2em] text-sm">Generation Notice</h3>
        <p class="text-slate-400 text-xs leading-relaxed font-bold">{{ adventure.creation_error }}</p>
        <button @click="emit('clear-creation-error')" class="text-[10px] text-slate-500 hover:text-white uppercase tracking-widest mt-2 transition-colors flex items-center gap-2">
          <X class="w-3 h-3" />
          Dismiss this notice
        </button>
      </div>
    </div>

    <!-- Quick Settings Row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Chronicle Title</label>
        <div v-if="editingField === 'title'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="$emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all" />
          <button @click="emit('save-field')" :disabled="isSaving" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'title', form.title)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span class="text-sm font-bold text-white">{{ form.title }}</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Version</label>
        <div v-if="editingField === 'version'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="$emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" maxlength="15" placeholder="e.g. 1.0.0" class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all" />
          <button @click="emit('save-field')" :disabled="isSaving" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'version', form.version)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span v-if="form.version" class="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 uppercase tracking-widest">v{{ form.version }}</span>
          <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No version set</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>
      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">In-Game Pacing ({{ form.time_per_turn }}m)</label>
          <div v-if="form.time_per_turn !== adventure?.time_per_turn" class="flex gap-2 animate-fade-in">
            <button @click="emit('update:pacing', adventure.time_per_turn)" class="text-xs font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
            <button @click="emit('save-changes')" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
          </div>
        </div>
        <input :value="form.time_per_turn" @input="handlePacingInput" type="range" min="1" max="60" class="w-full accent-emerald-500 h-2 bg-black/40 rounded-lg appearance-none cursor-pointer mt-3" />
      </div>
      <div class="space-y-2 flex flex-col justify-center">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Active Style</label>
        <div class="flex items-center gap-2">
          <div class="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-400 uppercase tracking-widest">
            {{ imageStylesCatalog.find(s => s.id === form.selected_style_id)?.name || 'Default' }}
          </div>
          <span class="text-[10px] text-slate-600 uppercase font-black">Scroll down to change</span>
        </div>
      </div>
    </div>

    <!-- Visual Style Gallery -->
    <section v-if="imageStylesCatalog.length" class="space-y-6 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
       <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
             <div class="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                <i class="ra ra-eye-shield text-emerald-500"></i>
             </div>
             <div>
                <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Visual Atmosphere</h3>
                <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Select the aesthetic direction for generated images</p>
             </div>
          </div>
          <div v-if="form.selected_style_id !== (adventure?.selected_image_styles?.[0]?.id || '')" class="flex gap-4 animate-fade-in">
             <button @click="emit('update:style', adventure?.selected_image_styles?.[0]?.id || '')" class="px-4 py-2 rounded-xl bg-slate-800 text-xs font-black text-slate-400 uppercase tracking-widest hover:text-white transition-all">Discard</button>
             <button @click="emit('save-changes')" class="px-6 py-2 rounded-xl bg-emerald-600 text-xs font-black text-white uppercase tracking-widest hover:bg-emerald-500 transition-all shadow-lg shadow-emerald-900/40">Apply Style</button>
          </div>
       </div>
       <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
          <button 
            v-for="style in imageStylesCatalog" 
            :key="style.id" 
            @click="emit('update:style', style.id)"
            class="relative aspect-[4/5] rounded-2xl overflow-hidden border-2 transition-all duration-500 group"
            :class="form.selected_style_id === style.id ? 'border-emerald-500 ring-4 ring-emerald-500/20' : 'border-transparent hover:border-white/10'"
          >
            <img :src="style.image_url" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80 group-hover:opacity-40 transition-opacity"></div>
            <div class="absolute bottom-3 left-3 right-3">
              <p class="text-[10px] font-black text-white uppercase tracking-tighter truncate">{{ style.name }}</p>
            </div>
            <div v-if="form.selected_style_id === style.id" class="absolute top-2 right-2 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center shadow-lg">
              <i class="ra ra-checkmark text-[10px] text-white"></i>
            </div>
          </button>
       </div>
    </section>

    <!-- Assets Section -->
    <div v-if="debugData" class="space-y-12">
      <!-- Cover -->
      <section v-if="debugData.adventure" class="space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Essence</h3>
          <button @click="emit('regen-all', 'cover')" :disabled="isBatchGenerating['cover']" class="px-4 py-2 rounded-xl bg-white/5 hover:bg-emerald-500/10 border border-white/5 text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-2 transition-all">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['cover'] }"></i>
            Regenerate Cover
          </button>
        </div>
        <div class="relative group aspect-[3/2] bg-slate-900 border border-white/5 rounded-[2rem] overflow-hidden shadow-2xl max-w-2xl mx-auto">
          <img v-if="debugData.adventure.image_url" :src="buildVisualImageUrl(debugData.adventure.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-1000" />
          <div v-if="isQuickGenerating['cover_' + debugData.adventure.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
            <div class="flex flex-col items-center gap-2">
              <i class="ra ra-cycle animate-spin text-3xl text-emerald-500"></i>
              <span class="text-xs font-black text-emerald-500 uppercase tracking-widest">Reweaving Essence...</span>
            </div>
          </div>
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent"></div>
          <div class="absolute inset-x-0 bottom-0 p-6">
            <div class="flex justify-between items-end gap-12">
              <div class="space-y-2 max-w-3xl">
                <h4 class="text-xl font-black text-white tracking-tight">{{ debugData.adventure.title }}</h4>
                <div class="flex items-center gap-3">
                  <p v-if="debugData.adventure.teaser" class="text-xs font-bold text-emerald-500/80 uppercase tracking-widest">{{ debugData.adventure.teaser }}</p>
                  <p v-else class="text-xs font-bold text-slate-500/40 uppercase tracking-widest italic">No teaser set...</p>
                  <button @click="emit('open-text-edit', 'cover', debugData.adventure.id, debugData.adventure.title, getCoverNarrativeContext(), debugData.adventure.teaser)" class="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-emerald-400 transition-all" title="Edit Teaser & Metadata">
                    <i class="ra ra-quill-ink text-xs"></i>
                  </button>
                </div>
                <p class="text-sm text-slate-400 leading-relaxed line-clamp-1">{{ getCoverNarrativeContext() }}</p>
              </div>
              <div class="relative shrink-0">
                 <button @click="emit('toggle-menu', debugData.adventure.id, $event)" class="w-10 h-10 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                    <div class="flex flex-col gap-0.5">
                      <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                      <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                      <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                    </div>
                  </button>
                  
                  <div v-if="activeMenuId === debugData.adventure.id" class="absolute right-0 bottom-full mb-3 w-56 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-2 z-50 animate-fade-in ring-1 ring-white/10">
                     <button @click="emit('quick-regen', 'cover', debugData.adventure.id)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-emerald-600 hover:text-white transition-all uppercase tracking-widest">Quick Regenerate</button>
                     <button @click="emit('open-regen-dialog', 'cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-cyan-600 hover:text-white transition-all uppercase tracking-widest">Regenerate (Prompt)</button>
                     <button @click="emit('open-upload-picker', 'cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-amber-600 hover:text-white transition-all uppercase tracking-widest">Upload Custom Cover</button>
                    <button v-if="debugData.adventure.image_url" @click="emit('download-asset', debugData.adventure.image_url, `${debugData.adventure.title || 'adventure'}_cover`)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-violet-600 hover:text-white transition-all uppercase tracking-widest">Download Cover</button>
                     <button @click="emit('open-text-edit', 'cover', debugData.adventure.id, debugData.adventure.title, getCoverNarrativeContext(), debugData.adventure.teaser)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-blue-600 hover:text-white transition-all uppercase tracking-widest">Edit Essence Details</button>
                  </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Categorized Grid -->
      <div class="space-y-8">
         <!-- Protagonist (Compact) -->
         <section v-if="debugData.protagonist" class="space-y-3">
           <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">The Protagonist</h3>
           <div class="max-w-[200px]">
                <div @mouseenter="emit('handle-hover', { name: debugData.protagonist.name, description: debugData.protagonist.description, image_url: debugData.protagonist.profile_image, type: 'PROTAGONIST', stats: { hp: debugData.protagonist.hp, stamina: debugData.protagonist.stamina, mana: debugData.protagonist.mana } }, $event)" @mouseleave="emit('clear-hover')" class="relative group aspect-square bg-slate-900 border border-white/5 rounded-xl overflow-hidden shadow-lg">
                  <img v-if="debugData.protagonist.profile_image" :src="buildVisualImageUrl(debugData.protagonist.profile_image)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                  <div v-if="isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                     <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
                  </div>
                  <div class="absolute inset-x-0 bottom-0 p-3">
                    <div class="font-black text-sm text-white tracking-tight truncate">{{ debugData.protagonist.name }}</div>
                  </div>
                  
                  <!-- Context Menu -->
                  <div class="absolute top-2 right-2 z-40">
                    <button @click="emit('toggle-menu', debugData.protagonist.id, $event)" class="w-8 h-8 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                      <div class="flex flex-col gap-0.5">
                        <div class="w-1 h-1 bg-white rounded-full"></div>
                        <div class="w-1 h-1 bg-white rounded-full"></div>
                        <div class="w-1 h-1 bg-white rounded-full"></div>
                      </div>
                    </button>
                    
                    <div v-if="activeMenuId === debugData.protagonist.id" class="absolute right-0 mt-2 w-48 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                       <button @click="emit('quick-regen', 'protagonist', debugData.protagonist.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate</button>
                       <button @click="emit('open-regen-dialog', 'protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
                       <button @click="emit('open-upload-picker', 'protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Portrait</button>
                        <button v-if="debugData.protagonist.profile_image" @click="emit('download-asset', debugData.protagonist.profile_image, `${debugData.protagonist.name || 'protagonist'}_portrait`)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Portrait</button>
                       <button @click="emit('open-text-edit', 'protagonist', debugData.protagonist.id, debugData.protagonist.name, debugData.protagonist.description, '', debugData.protagonist.hp, debugData.protagonist.stamina, debugData.protagonist.mana)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Character</button>
                    </div>
                  </div>
                </div>
           </div>
         </section>

         <!-- Scenes -->
         <section v-if="editorScenes.length" class="space-y-6">
           <div class="flex items-center justify-between">
             <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Locations ({{ editorScenes.length }})</h3>
             <button @click="emit('regen-all', 'scene')" :disabled="isBatchGenerating['scene']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
               <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['scene'] }"></i> Regenerate All
             </button>
           </div>
             <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
              <div v-for="scene in editorScenes" :key="'scene_' + scene.id" @mouseenter="emit('handle-hover', { id: scene.id, name: scene.label || scene.name, description: scene.description, image_url: scene.image_url, type: 'LOCATION' }, $event)" @mouseleave="emit('clear-hover')" class="relative group aspect-[3/2] bg-slate-900 border border-white/5 rounded-2xl shadow-xl transition-all overflow-visible">
                <div class="absolute inset-0 rounded-2xl overflow-hidden">
                  <img v-if="scene.image_url" :src="buildVisualImageUrl(scene.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                  <div v-if="isQuickGenerating['scene_' + scene.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                     <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
                  </div>
                  <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent opacity-80"></div>
                  <div class="absolute inset-x-0 bottom-0 p-4">
                    <div class="font-black text-sm text-white tracking-wide uppercase truncate drop-shadow-md">{{ scene.label || scene.name }}</div>
                  </div>
                </div>
                
                <!-- Context Menu -->
                <div class="absolute top-3 right-3 z-40">
                  <button @click="emit('toggle-menu', scene.id, $event)" class="w-8 h-8 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                    <div class="flex flex-col gap-0.5">
                      <div class="w-1 h-1 bg-white rounded-full"></div>
                      <div class="w-1 h-1 bg-white rounded-full"></div>
                      <div class="w-1 h-1 bg-white rounded-full"></div>
                    </div>
                  </button>
                  
                  <div v-if="activeMenuId === scene.id" class="absolute right-0 mt-2 w-48 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                     <button @click="emit('quick-regen', 'scene', scene.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate</button>
                     <button @click="emit('open-regen-dialog', 'scene', scene.id, scene.label || scene.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
                     <button @click="emit('open-upload-picker', 'scene', scene.id, scene.label || scene.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Illustration</button>
                    <button v-if="scene.image_url" @click="emit('download-asset', scene.image_url, `${scene.label || scene.name || 'scene'}_image`)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                     <button @click="emit('open-text-edit', 'scene', scene.id, scene.label || scene.name, scene.description)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Description</button>
                  </div>
                </div>
              </div>
            </div>
         </section>

         <!-- NPCs -->
         <section v-if="editorNpcs.length" class="space-y-6">
           <div class="flex items-center justify-between">
             <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Notable Inhabitants ({{ editorNpcs.length }})</h3>
             <button @click="emit('regen-all', 'npc')" :disabled="isBatchGenerating['npc']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
               <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['npc'] }"></i> Regenerate All
             </button>
           </div>
             <div class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
              <div v-for="npc in editorNpcs" :key="'npc_' + npc.id" @mouseenter="emit('handle-hover', { id: npc.id, name: npc.name, description: npc.description, image_url: npc.image_url, type: 'NPC', stats: npc.stats, inventory: npc.inventory }, $event)" @mouseleave="emit('clear-hover')" class="relative group aspect-[3/4] bg-slate-900 border border-white/5 rounded-2xl shadow-lg transition-all overflow-visible">
                <div class="absolute inset-0 rounded-2xl overflow-hidden">
                  <img v-if="npc.image_url" :src="buildVisualImageUrl(npc.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                  <div v-if="isQuickGenerating['npc_' + npc.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                    <i class="ra ra-cycle animate-spin text-xl text-emerald-500"></i>
                  </div>
                  <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
                  <div class="absolute bottom-0 left-0 right-0 p-3">
                    <div class="text-xs font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ npc.name }}</div>
                    <div v-if="npc.role" class="text-[9px] text-slate-300 font-bold uppercase tracking-tighter truncate opacity-70">{{ npc.role }}</div>
                    
                    <div v-if="ruleEnforcementMode !== 'chat' && npc.stats" class="flex gap-1.5 mt-1.5">
                      <template v-if="npc.stats.hp !== undefined">
                        <div class="flex items-center gap-1 text-[8px] font-black text-red-500 bg-red-500/10 px-1 py-0.5 rounded border border-red-500/20"><i class="ra ra-heart"></i> {{ npc.stats.hp }}</div>
                      </template>
                    </div>

                    <!-- NPC Inventory Icons -->
                    <div v-if="npc.inventory && npc.inventory.length > 0" class="flex flex-wrap gap-1 mt-2">
                      <div v-for="item in npc.inventory.slice(0, 4)" :key="item.id" class="w-4 h-4 rounded-sm overflow-hidden border border-white/10 bg-black/40">
                        <img v-if="item.image_url" :src="buildVisualImageUrl(item.image_url)" class="w-full h-full object-cover" />
                        <div v-else class="w-full h-full flex items-center justify-center">
                          <i :class="['ra text-[8px]', getItemIcon(item.item_type), 'text-slate-500']"></i>
                        </div>
                      </div>
                      <div v-if="npc.inventory.length > 4" class="text-[8px] text-slate-500 font-bold self-center ml-0.5">+{{ npc.inventory.length - 4 }}</div>
                    </div>
                  </div>
                </div>

                <!-- Context Menu -->
                <div class="absolute top-2 right-2 z-40">
                  <button @click="emit('toggle-menu', npc.id, $event)" class="w-8 h-8 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                    <div class="flex flex-col gap-0.5">
                      <div class="w-1 h-1 bg-white rounded-full group-hover/dots:bg-white"></div>
                      <div class="w-1 h-1 bg-white rounded-full group-hover/dots:bg-white"></div>
                      <div class="w-1 h-1 bg-white rounded-full group-hover/dots:bg-white"></div>
                    </div>
                  </button>
                  
                  <div v-if="activeMenuId === npc.id" class="absolute right-0 mt-2 w-48 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                     <button @click="emit('quick-regen', 'npc', npc.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate</button>
                     <button @click="emit('open-regen-dialog', 'npc', npc.id, npc.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
                     <button @click="emit('open-upload-picker', 'npc', npc.id, npc.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                    <button v-if="npc.image_url" @click="emit('download-asset', npc.image_url, `${npc.name || 'npc'}_image`)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                     <button @click="emit('open-text-edit', 'npc', npc.id, npc.name, npc.description, '', npc.hp, npc.stamina, npc.mana, npc.voice, npc.goal, npc.character)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
                  </div>
                </div>
              </div>
            </div>
         </section>

         <!-- Items -->
         <section v-if="editorObjects.length" class="space-y-6">
           <div class="flex items-center justify-between">
             <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Mystical Objects ({{ editorObjects.length }})</h3>
             <button @click="emit('regen-all', 'object')" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
               <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Regenerate All
             </button>
           </div>
             <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
              <div v-for="obj in editorObjects" :key="'obj_' + obj.id" @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)" @mouseleave="emit('clear-hover')" class="relative group aspect-square bg-slate-900 border border-white/5 rounded-xl shadow-lg transition-all overflow-visible">
                <div class="absolute inset-0 rounded-xl overflow-hidden">
                  <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                  <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                    <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
                  </div>
                  <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
                  <div class="absolute bottom-0 left-0 right-0 p-2">
                    <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
                    
                    <div v-if="ruleEnforcementMode !== 'chat' && obj.stats && Object.keys(obj.stats).length > 0" class="flex gap-1 mt-1">
                      <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.5)]"></div>
                    </div>
                  </div>
                </div>

                <!-- Context Menu -->
                <div class="absolute top-1.5 right-1.5 z-40">
                  <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                    <div class="flex flex-col gap-0.5">
                      <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                      <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                      <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                    </div>
                  </button>
                  
                  <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                     <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                     <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                     <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                    <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                     <button @click="emit('open-text-edit', 'object', obj.id, obj.name, obj.description)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
                  </div>
                </div>
              </div>
            </div>
         </section>

         <!-- Quests -->
         <section v-if="adventure?.quests?.length" class="space-y-6">
           <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Quest Log ({{ adventure.quests.length }})</h3>
           <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
             <div v-for="quest in adventure.quests" :key="'quest_' + quest.id" class="bg-slate-900/40 border border-white/5 rounded-2xl p-4 hover:border-emerald-500/20 transition-all group">
               <div class="flex items-start justify-between mb-2">
                 <div class="flex items-center gap-3">
                   <div class="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                     <i :class="[quest.is_main ? 'ra ra-trophy text-emerald-400' : 'ra ra-scroll-unfurled text-slate-400']"></i>
                   </div>
                   <div>
                     <h4 class="text-sm font-bold text-white">{{ quest.title }}</h4>
                     <span class="text-xs text-slate-500 uppercase tracking-widest">{{ quest.is_main ? 'Main Quest' : 'Side Quest' }}</span>
                   </div>
                 </div>
                 <span class="px-2 py-0.5 rounded bg-black/40 text-xs font-black text-emerald-500 uppercase border border-emerald-500/20">{{ quest.exp_reward }} XP</span>
               </div>
               <p class="text-xs text-slate-400 leading-relaxed line-clamp-2 mb-3">{{ quest.description }}</p>
               <div class="flex items-center gap-2">
                  <div class="flex-grow h-1 bg-black/40 rounded-full overflow-hidden">
                     <div class="h-full bg-emerald-500/40" :style="{ width: quest.status === 'completed' ? '100%' : '0%' }"></div>
                  </div>
                  <span class="text-xs font-black uppercase tracking-tighter" :class="quest.status === 'completed' ? 'text-emerald-500' : 'text-slate-600'">{{ quest.status }}</span>
               </div>
             </div>
           </div>
         </section>

         <!-- Awards (Read-only) -->
         <section v-if="adventure?.awards?.length" class="space-y-6">
           <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Achievements & Awards ({{ adventure.awards.length }})</h3>
           <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
             <div v-for="award in adventure.awards" :key="'award_' + award.key" class="bg-slate-900/40 border border-white/5 rounded-2xl p-5 hover:border-emerald-500/20 transition-all group flex items-start gap-4">
               <div :class="[
                 'w-12 h-12 rounded-xl flex items-center justify-center border shrink-0',
                 award.tier === 'gold' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' :
                 award.tier === 'silver' ? 'bg-slate-300/10 border-slate-300/20 text-slate-300' :
                 'bg-orange-700/10 border-orange-700/20 text-orange-700'
               ]">
                 <img :src="getAwardIcon(award.tier)" class="w-8 h-8 object-contain" alt="Trophy" />
               </div>
               <div class="space-y-1">
                 <div class="flex items-center gap-2">
                   <h4 class="text-sm font-black text-white uppercase tracking-tight">{{ award.title }}</h4>
                   <span :class="[
                     'text-xs font-black uppercase px-1.5 py-0.5 rounded border',
                     award.tier === 'gold' ? 'bg-amber-500/20 border-amber-500/30 text-amber-500' :
                     award.tier === 'silver' ? 'bg-slate-300/20 border-slate-300/30 text-slate-300' :
                     'bg-orange-700/20 border-orange-700/30 text-orange-700'
                   ]">{{ award.tier }}</span>
                 </div>
                 <p class="text-xs text-slate-400 leading-relaxed">{{ award.description }}</p>
                 <p class="text-xs text-slate-500 italic mt-1">Requirement: {{ award.requirement }}</p>
               </div>
             </div>
           </div>
         </section>

      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.animate-fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
