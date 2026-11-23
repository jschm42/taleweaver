<script setup lang="ts">
/**
 * Cut-scenes: slide shows (image + text, optional audio track) shown over the play view when a
 * chapter starts (the chapter's start cut-scene) or when a script calls tw.cutscene.play(id).
 * The list is edited as one draft and saved through the save bar; drawing an image runs at
 * once and puts the image into the draft. Spec: docs/specs/cutscenes.md.
 */
import { computed, ref } from 'vue'
import { Clapperboard, Plus } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { useConfirm, usePrompt } from '@/composables/useDialogs'
import { useDraft } from '@/composables/useDraft'
import { useToast } from '@/composables/useToast'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { cutsceneService, cutscenesOf, newCutscene } from '@/services/cutsceneService'
import { resolveAccent, resolveSkin } from '@/skins/skinRegistry'
import type { Cutscene, CutsceneDefinition } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiSaveBar from '@/components/ui/UiSaveBar.vue'
import CutsceneForm from '@/components/editor/cutscenes/CutsceneForm.vue'
import CutsceneOverlay from '@/components/game/immersive/CutsceneOverlay.vue'

interface CutscenesDraft {
  cutscenes: CutsceneDefinition[]
}

const editor = useEditor()
const confirm = useConfirm()
const prompt = usePrompt()
const toast = useToast()

const adventure = computed(() => editor.debugData?.adventure as Record<string, any> | undefined)

const { draft, isDirty, changedCount, isSaving, reset, commit } = useDraft<CutscenesDraft>(() => ({
  cutscenes: cutscenesOf(adventure.value),
}))
useUnsavedGuard(isDirty)

// By position: the id itself can be edited.
const selectedIndex = ref(-1)
const preview = ref<Cutscene | null>(null)

const cutscenes = computed(() => draft.value.cutscenes)
const selected = computed(() => cutscenes.value[selectedIndex.value] ?? null)
const styleNames = computed(() =>
  ((editor.imageStylesCatalog || []) as { name?: string, id?: string }[]).map((s) => s.name || s.id || '').filter(Boolean),
)
const audioTracks = computed(() =>
  ((adventure.value?.audio_tracks || []) as { id: string, name?: string, url?: string | null }[]).filter((t) => t.url),
)
const chapters = computed(() => (editor.adventure?.sequences || []) as { title?: string, id?: string, start_cutscene_id?: string }[])

function usedBy(id: string): string[] {
  return chapters.value.filter((c) => c.start_cutscene_id === id).map((c) => c.title || c.id || '')
}

const previewSkin = computed(() => resolveSkin('auto', adventure.value?.ui_theme, adventure.value?.selected_tone))
const previewSkinStyle = computed((): Record<string, string> => {
  const accent = resolveAccent('auto', adventure.value?.ui_theme)
  if (!accent) return {}
  return { '--tw-accent': accent, '--tw-accent-soft': accent }
})

async function addCutscene(): Promise<void> {
  const title = await prompt({
    title: 'New cut-scene',
    label: 'Title',
    placeholder: 'e.g. The Crimson Debt',
    validate: (v) => (v.trim() ? null : 'Enter a title.'),
  })
  if (!title) return
  const cutscene = newCutscene(title.trim(), new Set(cutscenes.value.map((c) => c.id)))
  draft.value.cutscenes.push(cutscene)
  selectedIndex.value = draft.value.cutscenes.length - 1
}

async function deleteCutscene(cutscene: CutsceneDefinition): Promise<void> {
  const chapterTitles = usedBy(cutscene.id)
  const ok = await confirm({
    title: `Delete ${cutscene.title || cutscene.id}?`,
    message: chapterTitles.length
      ? `It starts ${chapterTitles.join(', ')}; those chapters then start without a cut-scene. Removed when you save.`
      : 'The cut-scene is removed when you save.',
    confirmLabel: 'Delete cut-scene',
    danger: true,
  })
  if (!ok) return
  draft.value.cutscenes = cutscenes.value.filter((c) => c !== cutscene)
  selectedIndex.value = -1
}

function openPreview(cutscene: CutsceneDefinition): void {
  const track = audioTracks.value.find((t) => t.id === cutscene.audio_track_id)
  preview.value = {
    token: `preview-${Date.now()}`,
    id: cutscene.id,
    title: cutscene.title,
    slides: cutscene.slides.map((s) => ({ id: s.id, text: s.text, image_url: getImageUrl(s.image_url) || s.image_url })),
    audio: track?.url ? { id: track.id, url: track.url } : null,
  }
}

async function save(): Promise<void> {
  if (new Set(cutscenes.value.map((c) => c.id)).size !== cutscenes.value.length) {
    toast.warn('Two cut-scenes share an id. Give each its own id, then save.')
    return
  }
  try {
    await commit(async (value) => {
      await cutsceneService.saveCutscenes(editor.adventureId, value.cutscenes)
      await editor.fetchDebugInfo()
    })
    toast.success('Cut-scenes saved.')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to save the cut-scenes.')
  }
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader title="Cut-scenes" description="Slide shows with narration that open a chapter or that a script plays.">
      <template #actions>
        <UiButton variant="primary" :icon="Plus" @click="addCutscene">New cut-scene</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="!cutscenes.length"
      :icon="Clapperboard"
      title="No cut-scene yet"
      description="Create one, then pick it as a chapter's start cut-scene or play it from a script."
    />

    <template v-else>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <button
          v-for="(cutscene, index) in cutscenes"
          :key="index"
          type="button"
          :class="[
            'flex gap-3 rounded-xl border bg-wb-surface p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
            index === selectedIndex ? 'border-wb-accent' : 'border-wb-line hover:border-wb-line-strong',
          ]"
          @click="selectedIndex = index"
        >
          <span class="relative aspect-[16/9] w-24 shrink-0 overflow-hidden rounded-md bg-wb-sunken">
            <img
              v-if="cutscene.slides[0]?.image_url"
              :src="getImageUrl(cutscene.slides[0].image_url) || cutscene.slides[0].image_url || ''"
              alt=""
              class="absolute inset-0 h-full w-full object-cover"
            />
          </span>
          <span class="min-w-0">
            <span class="wb-label block truncate !text-wb-strong">{{ cutscene.title || cutscene.id }}</span>
            <span class="wb-mono block truncate text-wb-muted">{{ cutscene.id }}</span>
            <span class="wb-hint block">{{ cutscene.slides.length }} slide{{ cutscene.slides.length === 1 ? '' : 's' }}</span>
          </span>
        </button>
      </div>

      <UiCard v-if="selected" :title="selected.title || selected.id">
        <CutsceneForm
          :key="selectedIndex"
          v-model="draft.cutscenes[selectedIndex]"
          :adventure-id="editor.adventureId"
          :other-ids="cutscenes.filter((c) => c !== selected).map((c) => c.id)"
          :style-names="styleNames"
          :audio-tracks="audioTracks"
          :used-by="usedBy(selected.id)"
          @preview="openPreview(selected)"
          @delete="deleteCutscene(selected)"
        />
      </UiCard>
      <p v-else class="wb-hint">Select a cut-scene to edit it.</p>
    </template>

    <CutsceneOverlay
      :cutscene="preview"
      :auto-speech="false"
      :skin="previewSkin"
      :skin-style="previewSkinStyle"
      @finished="preview = null"
    />

    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
