<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronUp, MapPin, Save } from 'lucide-vue-next'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'

/**
 * Editor for the scenes' helper blocks (helpers_script): functions and constants that, like the
 * init_script definitions, are loaded before every script run, wherever the player is.
 */
const props = defineProps<{
  scenes: any[]
  isSaving?: boolean
}>()

const emit = defineEmits<{
  (e: 'save', sceneId: string, helpersScript: string): void
}>()

const sceneLabel = (scene: any) => String(scene?.label || scene?.name || scene?.id || '')
const helpersOf = (scene: any) => String(scene?.helpers_script || '')
const countFunctions = (code: string) => (code.match(/^def\s+\w+/gm) || []).length

const sortedScenes = computed(() =>
  [...(props.scenes || [])].filter((s) => s?.id).sort((a, b) => sceneLabel(a).localeCompare(sceneLabel(b))),
)
const scenesWithHelpers = computed(() => sortedScenes.value.filter((s) => helpersOf(s).trim()))

const selectedId = ref<string>(scenesWithHelpers.value[0]?.id || sortedScenes.value[0]?.id || '')
const selectedScene = computed(() => sortedScenes.value.find((s) => String(s.id) === selectedId.value))
const savedCode = computed(() => helpersOf(selectedScene.value))
const draft = ref(savedCode.value)
const expanded = ref(scenesWithHelpers.value.length > 0)

// Reload the draft when another scene is picked or the saved value changes after a save.
watch(savedCode, (value) => {
  draft.value = value
})
watch(sortedScenes, (scenes) => {
  if (!scenes.some((s) => String(s.id) === selectedId.value)) {
    selectedId.value = scenes[0]?.id || ''
  }
})

const isDirty = computed(() => draft.value.trim() !== savedCode.value.trim())

function selectScene(id: string) {
  if (isDirty.value && !window.confirm('Discard the unsaved helpers of this scene?')) return
  selectedId.value = id
  draft.value = savedCode.value
}
</script>

<template>
  <div class="bg-slate-900/60 border border-white/10 rounded-2xl backdrop-blur-md">
    <button
      type="button"
      class="w-full flex items-center gap-3 px-6 py-4 text-left"
      @click="expanded = !expanded"
    >
      <div class="w-8 h-8 rounded-lg bg-sky-500/20 border border-sky-500/40 flex items-center justify-center shrink-0">
        <MapPin class="w-4 h-4 text-sky-300" />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-black text-white flex items-center gap-2">
          Scene Helpers
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/15 border border-sky-500/30 text-sky-300 font-bold">
            {{ scenesWithHelpers.length }} {{ scenesWithHelpers.length === 1 ? 'scene' : 'scenes' }}
          </span>
          <span v-if="isDirty" class="text-[10px] text-amber-300 font-bold">unsaved</span>
        </p>
        <p class="text-[11px] text-slate-400">
          Per-scene functions and constants, loaded after the init script before every script, wherever
          the player is. Good for a scene's puzzle logic and its choice-dialog handlers.
        </p>
      </div>
      <component :is="expanded ? ChevronUp : ChevronDown" class="w-4 h-4 text-slate-500 shrink-0" />
    </button>

    <div v-if="expanded" class="px-6 pb-5 space-y-3 border-t border-white/5 pt-4">
      <p v-if="!sortedScenes.length" class="text-xs text-slate-500">This adventure has no scenes yet.</p>
      <template v-else>
        <div class="flex flex-col sm:flex-row sm:items-center gap-3">
          <label class="text-[10px] font-black text-slate-400 uppercase tracking-widest shrink-0" for="scene-helpers-scene">Scene</label>
          <select
            id="scene-helpers-scene"
            :value="selectedId"
            class="flex-1 min-w-0 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-sky-500 outline-none"
            @change="selectScene(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="scene in sortedScenes" :key="scene.id" :value="scene.id">
              {{ sceneLabel(scene) }} ({{ scene.id }}){{ helpersOf(scene).trim() ? ` · ${countFunctions(helpersOf(scene))} fn` : '' }}
            </option>
          </select>
        </div>
        <div v-if="scenesWithHelpers.length" class="flex flex-wrap gap-1.5">
          <button
            v-for="scene in scenesWithHelpers"
            :key="'chip-' + scene.id"
            type="button"
            :class="[
              'px-2 py-0.5 rounded-full text-[10px] font-bold border transition-colors',
              String(scene.id) === selectedId
                ? 'bg-sky-500/25 border-sky-400/60 text-sky-100'
                : 'bg-white/5 border-white/10 text-slate-400 hover:text-white',
            ]"
            @click="selectScene(String(scene.id))"
          >
            {{ sceneLabel(scene) }}
          </button>
        </div>
        <ScriptEditor
          v-model="draft"
          :label="`helpers_script · ${selectedId}`"
          help-text="Only def statements and constant assignments (NAME = value) are loaded; other statements never run. Prefix names with the scene to avoid clashes."
          context="init_script"
          placeholder="def crypt_curse():&#10;    tw.player.damage(8)&#10;    tw.vars.set('crypt_cursed', True)"
          min-height="180px"
        />
        <div class="flex items-center justify-end gap-3">
          <button
            type="button"
            :disabled="!isDirty || isSaving"
            class="px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider text-slate-400 hover:text-white disabled:opacity-40 transition-colors"
            @click="draft = savedCode"
          >
            Revert
          </button>
          <button
            type="button"
            :disabled="!isDirty || isSaving || !selectedId"
            class="flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-black uppercase tracking-wider disabled:opacity-40 transition-colors"
            @click="emit('save', selectedId, draft)"
          >
            <Save class="w-3.5 h-3.5" />
            Save Scene Helpers
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
