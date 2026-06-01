<script setup lang="ts">
import { getItemIcon } from '@/utils/game_icons'

const props = defineProps<{
  editorObjects: any[]
  editorSwitches: any[]
  editorContainers: any[]
  editorTextLogs: any[]
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  ruleEnforcementMode: string
  visualsCacheVersion: number
}>()

const emit = defineEmits<{
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'regen-all', kind: string, missingOnly?: boolean): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'handle-hover', entity: any, event: MouseEvent): void
  (e: 'clear-hover'): void
}>()

const isContainerLocked = (obj: any): boolean => {
  if (String(obj?.item_type || '').toUpperCase() !== 'CONTAINER') return false
  if (typeof obj?.locked === 'boolean') return obj.locked
  const metadata = (obj?.metadata_json && typeof obj.metadata_json === 'object') ? obj.metadata_json : {}
  return Boolean(metadata.code_to_unlock || metadata.item_to_unlock)
}

const hasMissingImage = (obj: any): boolean => {
  const raw = String(obj?.image_url || '').trim()
  if (!raw) return true
  const lowered = raw.toLowerCase()
  if (lowered.startsWith('assets/') || lowered.startsWith('/assets/')) return true
  if (lowered.includes('placeholder_') || lowered.includes('/placeholder-')) return true
  return false
}

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return `${imagePath}?v=${props.visualsCacheVersion}`
}
</script>

<template>
  <section v-if="editorTextLogs.length || editorContainers.length || editorSwitches.length || editorObjects.length" class="space-y-8 animate-page-in">
    <!-- Text Logs Section -->
    <div v-if="editorTextLogs.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Text Logs ({{ editorTextLogs.length }})</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'text-log', true)" :disabled="isBatchGenerating['text-log']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'text-log', false)" :disabled="isBatchGenerating['text-log']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
        <div
          v-for="obj in editorTextLogs"
          :key="'txt_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: (obj.metadata_json?.text_log_content || obj.description), image_url: obj.image_url, type: 'TEXT_LOG', stats: {} }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-cyan-500/20 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-cyan-500/40 bg-cyan-500/20 text-cyan-200">LOG</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
              <div class="text-[9px] text-cyan-200/80 uppercase tracking-widest mt-1">{{ (obj.metadata_json?.text_log_format || 'DOCUMENT') }}</div>
            </div>
          </div>
          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-cyan-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, (obj.description || ''))" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Containers Section -->
    <div v-if="editorContainers.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Containers ({{ editorContainers.length }})</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'container', true)" :disabled="isBatchGenerating['container']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'container', false)" :disabled="isBatchGenerating['container']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        <div
          v-for="obj in editorContainers"
          :key="'con_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-amber-500/20 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div v-if="isContainerLocked(obj)" class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-amber-400/50 bg-amber-500/25 text-amber-100 z-10">LOCKED</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
            </div>
          </div>
          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'container'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, obj.description)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Switches Section -->
    <div v-if="editorSwitches.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Switches ({{ editorSwitches.length }})</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'switch', true)" :disabled="isBatchGenerating['switch']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'switch', false)" :disabled="isBatchGenerating['switch']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        <div
          v-for="obj in editorSwitches"
          :key="'sw_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-lime-500/20 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-lime-400/50 bg-lime-500/25 text-lime-100 z-10">SWITCH</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
              <div class="text-[9px] text-lime-200/80 uppercase tracking-widest mt-1">{{ String(obj.item_type || 'SWITCH').toUpperCase() }}</div>
            </div>
          </div>

          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'switch'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, obj.description)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Mystical Objects Section -->
    <div v-if="editorObjects.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Mystical Objects ({{ editorObjects.length }})</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'object', true)" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'object', false)" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        <div
          v-for="obj in editorObjects"
          :key="'obj_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-white/5 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
              <div v-if="ruleEnforcementMode !== 'chat' && obj.stats && Object.keys(obj.stats).length > 0" class="flex gap-1 mt-1">
                <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.5)]"></div>
              </div>
            </div>
          </div>

          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, obj.description)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
            </div>
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
