<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  editorScenes: any[]
  debugData?: any
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  visualsCacheVersion: number
}>()

const emit = defineEmits<{
  (e: 'regen-all', kind: string, missingOnly?: boolean): void
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'handle-hover', entity: any, event: MouseEvent): void
  (e: 'clear-hover'): void
}>()

const scenes = computed<any[]>(() => {
  const source = Array.isArray(props.debugData?.scenes) && props.debugData.scenes.length > 0
    ? props.debugData.scenes
    : props.editorScenes
  return Array.isArray(source) ? source : []
})

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return `${imagePath}?v=${props.visualsCacheVersion}`
}
</script>

<template>
  <section v-if="scenes.length" class="space-y-6 animate-page-in">
    <div class="flex items-center justify-between">
      <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Locations ({{ scenes.length }})</h3>
      <div class="flex items-center gap-4">
        <button @click="emit('regen-all', 'scene', true)" :disabled="isBatchGenerating['scene']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
          <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['scene'] }"></i> Generate Missing
        </button>
        <button @click="emit('regen-all', 'scene', false)" :disabled="isBatchGenerating['scene']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
          <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['scene'] }"></i> Regenerate All
        </button>
      </div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
      <div v-for="(scene, idx) in scenes" :key="'scene_' + (scene.id || idx)" @mouseenter="emit('handle-hover', { id: scene.id, name: scene.label || scene.name, description: scene.description, image_url: scene.image_url, type: 'LOCATION' }, $event)" @mouseleave="emit('clear-hover')" class="relative group aspect-[3/2] bg-slate-900 border border-white/5 rounded-2xl shadow-xl transition-all overflow-visible">
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
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
