<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import type { CatalogTile, CreateAdventurePayload } from '@/types'

const router = useRouter()

type RuleMode = 'strict' | 'moderate' | 'loose'

const form = ref({
  title: '',
  storyIdea: '',
  generate_npc_images: false,
  generate_item_images: false,
  generate_scene_images: false,
  automatic_cover_generation: false,
  clock_enabled: false,
  pacing_minutes: 5,
  rule_enforcement_mode: 'strict' as RuleMode,
  selected_image_styles: [] as string[],
  selected_tone: '',
})

const imageStylesCatalog = ref<CatalogTile[]>([])
const toneCatalog = ref<CatalogTile[]>([])

const isLoadingCatalogs = ref(true)
const isSubmitting = ref(false)
const errorMsg = ref('')
const statusMsg = ref('')

const ruleModeHelp = computed(() => {
  if (form.value.rule_enforcement_mode === 'strict') {
    return 'Der Gamemaster laesst keine Abweichung von den Regeln zu.'
  }
  if (form.value.rule_enforcement_mode === 'moderate') {
    return 'Der Gamemaster laesst einige kreative Ideen des Spielers zu.'
  }
  return 'Der Gamemaster kontrolliert Regeln locker und laesst kreative Loesungen zu.'
})

function toggleImageStyle(styleId: string) {
  if (form.value.selected_image_styles.includes(styleId)) {
    form.value.selected_image_styles = form.value.selected_image_styles.filter((id) => id !== styleId)
    return
  }
  form.value.selected_image_styles = [...form.value.selected_image_styles, styleId]
}

async function loadCatalogs() {
  isLoadingCatalogs.value = true
  try {
    const settings = await api.getSettings()
    imageStylesCatalog.value = settings.image_styles_catalog || []
    toneCatalog.value = settings.tone_catalog || []
    if (!form.value.selected_tone && toneCatalog.value.length > 0) {
      form.value.selected_tone = toneCatalog.value[0].id
    }
  } catch (error: any) {
    errorMsg.value = error?.message || 'Konfiguration konnte nicht geladen werden.'
  } finally {
    isLoadingCatalogs.value = false
  }
}

async function pollAdventureStatus(adventureId: string): Promise<void> {
  return new Promise((resolve) => {
    const interval = window.setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/adventures/${adventureId}/status`)
        if (!res.ok) {
          clearInterval(interval)
          errorMsg.value = 'Generierungsstatus konnte nicht geladen werden.'
          resolve()
          return
        }

        const data = await res.json()
        statusMsg.value = data.status || 'Constructing world...'
        if (data.error) {
          clearInterval(interval)
          errorMsg.value = `Generierung fehlgeschlagen: ${data.error}`
          resolve()
          return
        }

        if (data.is_ready) {
          clearInterval(interval)
          router.push({ name: 'game', params: { id: adventureId } })
          resolve()
        }
      } catch {
        clearInterval(interval)
        errorMsg.value = 'Verbindung beim Status-Polling verloren.'
        resolve()
      }
    }, 1500)
  })
}

async function createAdventure() {
  if (!form.value.title.trim()) {
    errorMsg.value = 'Title ist erforderlich.'
    return
  }
  if (form.value.pacing_minutes < 1 || form.value.pacing_minutes > 30) {
    errorMsg.value = 'Pacing muss zwischen 1 und 30 Minuten liegen.'
    return
  }

  isSubmitting.value = true
  errorMsg.value = ''
  statusMsg.value = 'Initializing...'

  const strictRules = form.value.rule_enforcement_mode === 'strict'
  const payload: CreateAdventurePayload = {
    title: form.value.title.trim(),
    context: form.value.storyIdea.trim(),
    strict_rules: strictRules,
    rule_enforcement_mode: form.value.rule_enforcement_mode,
    generate_npc_images: form.value.generate_npc_images,
    generate_item_images: form.value.generate_item_images,
    generate_scene_images: form.value.generate_scene_images,
    automatic_cover_generation: form.value.automatic_cover_generation,
    clock_enabled: form.value.clock_enabled,
    time_per_turn: form.value.pacing_minutes,
    pacing_minutes: form.value.pacing_minutes,
    selected_image_styles: form.value.selected_image_styles,
    selected_tone: form.value.selected_tone || undefined,
  }

  try {
    const result = await api.createAdventure(payload)
    await pollAdventureStatus(result.adventure_id)
  } catch (error: any) {
    errorMsg.value = error?.message || 'Adventure konnte nicht erstellt werden.'
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  void loadCatalogs()
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 md:p-10">
    <header class="w-full max-w-5xl mx-auto mb-8 flex items-center justify-between">
      <div>
        <h1 class="text-3xl md:text-4xl font-extrabold text-white">Neue Adventure-Generierung</h1>
        <p class="text-slate-400 mt-2">Ein Modus, klare Parameter, kontrollierbarer Stil und Tone.</p>
      </div>
      <button
        @click="router.push({ name: 'portal' })"
        class="px-4 py-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800"
      >
        Zurueck
      </button>
    </header>

    <main class="w-full max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-6">
      <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
        <div class="grid grid-cols-1 gap-5">
          <div>
            <label class="block text-sm font-semibold text-slate-300 mb-2">Title *</label>
            <input
              v-model="form.title"
              type="text"
              maxlength="70"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white"
            />
          </div>

          <div>
            <label class="block text-sm font-semibold text-slate-300 mb-2">Story Idea</label>
            <textarea
              v-model="form.storyIdea"
              rows="5"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"
            ></textarea>
          </div>
        </div>

        <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
          <h2 class="text-lg font-bold text-white">Regelmodus</h2>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <button
              @click="form.rule_enforcement_mode = 'strict'"
              :class="['text-left border rounded-lg p-3 transition-colors', form.rule_enforcement_mode === 'strict' ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-300']"
            >
              <div class="font-bold">Strikt</div>
              <div class="text-xs mt-1">Keine Regelabweichung</div>
            </button>
            <button
              @click="form.rule_enforcement_mode = 'moderate'"
              :class="['text-left border rounded-lg p-3 transition-colors', form.rule_enforcement_mode === 'moderate' ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-300']"
            >
              <div class="font-bold">Moderat</div>
              <div class="text-xs mt-1">Einige kreative Ausnahmen</div>
            </button>
            <button
              @click="form.rule_enforcement_mode = 'loose'"
              :class="['text-left border rounded-lg p-3 transition-colors', form.rule_enforcement_mode === 'loose' ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-300']"
            >
              <div class="font-bold">Locker</div>
              <div class="text-xs mt-1">Regeln nur leicht fuehren</div>
            </button>
          </div>
          <p class="text-xs text-slate-400">{{ ruleModeHelp }}</p>
        </div>

        <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-4">
          <h2 class="text-lg font-bold text-white">Spielzeit & Pacing</h2>
          <label class="flex items-center justify-between gap-3 text-sm">
            <span>Spielzeituhr aktivieren</span>
            <input type="checkbox" v-model="form.clock_enabled" />
          </label>
          <div>
            <div class="flex items-center justify-between text-sm mb-2">
              <span>Pacing pro Aktion</span>
              <strong class="text-emerald-400">{{ form.pacing_minutes }} Min</strong>
            </div>
            <input
              type="range"
              v-model.number="form.pacing_minutes"
              min="1"
              max="30"
              step="1"
              class="w-full accent-emerald-500"
            />
          </div>
        </div>

        <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2">
          <h2 class="text-lg font-bold text-white">Bildgenerierung</h2>
          <label class="flex items-center justify-between gap-3 text-sm">
            <span>Generate NPC Images</span>
            <input type="checkbox" v-model="form.generate_npc_images" />
          </label>
          <label class="flex items-center justify-between gap-3 text-sm">
            <span>Generate Item Images</span>
            <input type="checkbox" v-model="form.generate_item_images" />
          </label>
          <label class="flex items-center justify-between gap-3 text-sm">
            <span>Generate Scene Images</span>
            <input type="checkbox" v-model="form.generate_scene_images" />
          </label>
          <label class="flex items-center justify-between gap-3 text-sm">
            <span>Automatic Cover Generation</span>
            <input type="checkbox" v-model="form.automatic_cover_generation" />
          </label>
        </div>
      </section>

      <aside class="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
        <div>
          <h2 class="text-lg font-bold text-white">Bildstile</h2>
          <p class="text-xs text-slate-400">Mehrfachauswahl moeglich. Alle gewaehlten Stile werden kombiniert.</p>
        </div>

        <div v-if="isLoadingCatalogs" class="text-sm text-slate-500">Kataloge werden geladen...</div>

        <div v-else class="space-y-2 max-h-64 overflow-y-auto pr-1">
          <button
            v-for="style in imageStylesCatalog"
            :key="style.id"
            @click="toggleImageStyle(style.id)"
            :class="['w-full text-left border rounded-lg p-3 transition-colors', form.selected_image_styles.includes(style.id) ? 'border-cyan-500 bg-cyan-500/10 text-cyan-100' : 'border-slate-700 bg-slate-950 text-slate-300']"
          >
            <div class="font-semibold">{{ style.name }}</div>
            <div class="text-xs mt-1 text-slate-400">{{ style.description }}</div>
          </button>
        </div>

        <div>
          <h2 class="text-lg font-bold text-white">Tone</h2>
          <div class="space-y-2 mt-2 max-h-52 overflow-y-auto pr-1">
            <label
              v-for="tone in toneCatalog"
              :key="tone.id"
              class="flex items-start gap-3 border border-slate-700 rounded-lg p-3 bg-slate-950"
            >
              <input type="radio" name="tone" :value="tone.id" v-model="form.selected_tone" class="mt-1" />
              <div>
                <div class="font-semibold text-slate-100">{{ tone.name }}</div>
                <div class="text-xs text-slate-400">{{ tone.description }}</div>
              </div>
            </label>
          </div>
        </div>

        <div v-if="errorMsg" class="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-300">
          {{ errorMsg }}
        </div>

        <div class="space-y-3 pt-2">
          <button
            @click="createAdventure"
            :disabled="isSubmitting"
            class="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold disabled:opacity-50"
          >
            {{ isSubmitting ? (statusMsg || 'Generating...') : 'Adventure generieren' }}
          </button>
          <p v-if="statusMsg" class="text-xs text-slate-400">{{ statusMsg }}</p>
        </div>
      </aside>
    </main>
  </div>
</template>
