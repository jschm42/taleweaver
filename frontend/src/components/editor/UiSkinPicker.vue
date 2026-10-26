<script setup lang="ts">
/**
 * UiSkinPicker — Lets the author choose the in-game dialog skin and an optional accent
 * color for the adventure, with a live preview rendered by the real skin classes.
 * Saves itself via PATCH (only the whitelisted `ui_theme` field).
 */
import { ref, computed, watch } from 'vue'
import { Save, RotateCcw } from 'lucide-vue-next'
import { adventureService } from '@/services/adventureService'
import { useNotifications } from '@/composables/useNotifications'
import {
  SKINS,
  findSkin,
  isSkinId,
  skinForTone,
  toneLabel,
  type AdventureUiTheme,
  type SkinId,
} from '@/skins/skinRegistry'

const props = defineProps<{
  adventureId: string
  uiTheme?: AdventureUiTheme | null
  tone?: unknown
}>()

const emit = defineEmits<{
  (e: 'update:uiTheme', value: AdventureUiTheme | null): void
}>()

const { addNotification } = useNotifications()

const skin = ref<SkinId | 'auto'>('auto')
const accent = ref('')
const isSaving = ref(false)

function syncFromProps() {
  skin.value = isSkinId(props.uiTheme?.skin) ? props.uiTheme.skin : 'auto'
  accent.value = props.uiTheme?.accent || ''
}

watch(() => props.uiTheme, syncFromProps, { immediate: true })

const toneSkin = computed(() => skinForTone(props.tone))
const previewSkin = computed<SkinId>(() => (skin.value === 'auto' ? toneSkin.value : skin.value))
const previewStyle = computed(() => (accent.value ? { '--tw-accent': accent.value, '--tw-accent-soft': accent.value } : {}))
const accentPickerValue = computed(() => accent.value || '#f59e0b')

const payload = computed<AdventureUiTheme | null>(() => {
  const theme: AdventureUiTheme = {}
  if (skin.value !== 'auto') {
    theme.skin = skin.value
  }
  if (accent.value) {
    theme.accent = accent.value
  }
  return Object.keys(theme).length ? theme : null
})

const isDirty = computed(() => JSON.stringify(payload.value) !== JSON.stringify(normalized(props.uiTheme)))

function normalized(theme?: AdventureUiTheme | null): AdventureUiTheme | null {
  if (!theme) {
    return null
  }
  const clean: AdventureUiTheme = {}
  if (isSkinId(theme.skin)) {
    clean.skin = theme.skin
  }
  if (theme.accent) {
    clean.accent = theme.accent
  }
  return Object.keys(clean).length ? clean : null
}

function onAccentInput(event: Event) {
  accent.value = (event.target as HTMLInputElement).value.toLowerCase()
}

async function save() {
  isSaving.value = true
  try {
    await adventureService.updateAdventure(props.adventureId, { ui_theme: payload.value })
    emit('update:uiTheme', payload.value)
    addNotification('Game UI theme saved.', 'success')
  } catch {
    addNotification('Failed to save the game UI theme.', 'error')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <section class="space-y-6 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
    <div class="flex items-center justify-between gap-4">
      <div class="flex items-center gap-4">
        <div class="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
          <i class="ra ra-quill-ink text-amber-500"></i>
        </div>
        <div>
          <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Game UI Theme</h3>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Look of narration, dialogue and story tabs in game</p>
        </div>
      </div>
      <div v-if="isDirty" class="flex items-center gap-2 animate-fade-in">
        <button
          type="button"
          :disabled="isSaving"
          class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg disabled:opacity-50 flex items-center justify-center cursor-pointer"
          title="Save"
          @click="save"
        >
          <i v-if="isSaving" class="ra ra-cycle animate-spin text-sm"></i>
          <Save v-else class="w-4 h-4" />
        </button>
        <button
          type="button"
          :disabled="isSaving"
          class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white rounded-xl transition-all flex items-center justify-center cursor-pointer"
          title="Discard changes"
          @click="syncFromProps"
        >
          <RotateCcw class="w-4 h-4" />
        </button>
      </div>
    </div>

    <p class="text-xs leading-relaxed text-slate-400 max-w-3xl">
      <span class="font-bold text-slate-300">Auto</span> picks a skin from the narrative tone
      ({{ toneLabel(props.tone) || 'none selected' }} → {{ findSkin(toneSkin).label }}). Players can still override
      the skin in their in-game settings. Only built-in skins are available, so imported adventures cannot inject
      custom styles.
    </p>

    <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div class="space-y-4">
        <div role="radiogroup" aria-label="Game UI theme" class="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <button
            type="button"
            role="radio"
            :aria-checked="skin === 'auto'"
            class="rounded-xl border p-3 text-left transition-all cursor-pointer"
            :class="skin === 'auto' ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
            @click="skin = 'auto'"
          >
            <span class="block text-xs font-black uppercase tracking-widest text-white">Auto</span>
            <span class="block text-[11px] text-slate-400">From tone · {{ findSkin(toneSkin).label }}</span>
          </button>
          <button
            v-for="definition in SKINS"
            :key="definition.id"
            type="button"
            role="radio"
            :aria-checked="skin === definition.id"
            class="flex items-center gap-2.5 rounded-xl border p-3 text-left transition-all cursor-pointer"
            :class="skin === definition.id ? 'border-amber-400/70 bg-amber-500/10' : 'border-white/10 bg-white/[0.03] hover:border-white/20'"
            @click="skin = definition.id"
          >
            <span class="flex h-8 w-8 shrink-0 overflow-hidden rounded-md border border-white/10" aria-hidden="true">
              <span v-for="color in definition.swatch" :key="color" class="flex-1" :style="{ background: color }"></span>
            </span>
            <span class="text-xs font-black uppercase tracking-widest text-white">{{ definition.label }}</span>
          </button>
        </div>

        <div class="flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="color"
              :value="accentPickerValue"
              class="h-9 w-12 cursor-pointer rounded-lg border border-white/15 bg-transparent"
              aria-label="Accent color"
              @input="onAccentInput"
            />
            <span>
              <span class="block text-xs font-black uppercase tracking-widest text-white">Accent color</span>
              <span class="block text-[11px] text-slate-400">{{ accent || 'Skin default' }}</span>
            </span>
          </label>
          <button
            v-if="accent"
            type="button"
            class="ml-auto text-[11px] font-bold uppercase tracking-wider text-slate-400 hover:text-white cursor-pointer"
            @click="accent = ''"
          >
            Use skin default
          </button>
        </div>
      </div>

      <!-- Live preview with the real skin classes -->
      <div
        class="tw-skin relative overflow-hidden rounded-2xl border border-white/10 bg-slate-950 p-5 flex flex-col gap-4"
        :data-skin="previewSkin"
        :style="previewStyle"
        aria-label="Skin preview"
      >
        <div class="tw-scene-tint"></div>
        <div class="relative flex gap-2">
          <span class="tw-tab tw-tab--active">Story</span>
          <span class="tw-tab">Discoveries <span class="tw-tab-count">2</span><span class="tw-tab-dot"></span></span>
        </div>
        <div class="tw-narration relative">
          <div>
            <span class="tw-narration-label">Game Master</span>
            <span class="tw-narration-text">The lantern sputters as you step inside. Dust drifts through a single beam of moonlight.</span>
          </div>
        </div>
        <div class="tw-bubble relative ml-3">
          <svg class="tw-bubble-tail" viewBox="0 0 16 24" aria-hidden="true">
            <polygon points="16,0 0,12 16,24" />
            <rect x="14" y="1" width="4" height="22" />
          </svg>
          <p class="tw-bubble-text italic">
            <span class="tw-speaker tw-speaker--primary mr-1.5 font-black text-xs uppercase tracking-wider">Innkeeper</span>
            <span class="comic-voice-tag mr-1.5">wary</span>
            "We don't get many travellers this late."
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
