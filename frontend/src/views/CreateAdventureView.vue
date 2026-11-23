<script setup lang="ts">
/**
 * "Generate adventure": describe an idea and let the World-Builder create the world.
 * Simple mode shows story, play style and look; advanced mode adds time, world size and media.
 * State and actions: composables/createAdventure/; one component per section.
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpen, Clock, Copy, Dices, Image, Layers, Palette, Swords } from 'lucide-vue-next'
import { provideCreateAdventure } from '@/composables/createAdventure/createAdventureContext'
import { useCreateAdventure } from '@/composables/createAdventure/useCreateAdventure'
import type { GeneratorMode } from '@/composables/createAdventure/createAdventureForm'
import CoverSourceSection from '@/components/create-adventure/CoverSourceSection.vue'
import GenerateBar from '@/components/create-adventure/GenerateBar.vue'
import LookSection from '@/components/create-adventure/LookSection.vue'
import MediaSection from '@/components/create-adventure/MediaSection.vue'
import PlayStyleSection from '@/components/create-adventure/PlayStyleSection.vue'
import StorySection from '@/components/create-adventure/StorySection.vue'
import TimeSection from '@/components/create-adventure/TimeSection.vue'
import WorldSizeSection from '@/components/create-adventure/WorldSizeSection.vue'
import PageHeader from '@/components/workbench/PageHeader.vue'
import WorkbenchNav, { type WorkbenchNavGroup } from '@/components/workbench/WorkbenchNav.vue'
import WorkbenchShell from '@/components/workbench/WorkbenchShell.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'

const router = useRouter()
const state = useCreateAdventure()
provideCreateAdventure(state)
const { mode, isCoverMode, errorMsg, hasLlmConfig, isConfigLoaded, isSurprising, setMode, surpriseMe } = state

const MODES: { value: GeneratorMode; label: string }[] = [
  { value: 'simple', label: 'Simple' },
  { value: 'advanced', label: 'Advanced' },
]

const activeSection = ref('story')

const navGroups = computed<WorkbenchNavGroup[]>(() => {
  const basics = [
    ...(isCoverMode.value ? [{ id: 'cover', label: 'Based on', icon: Copy }] : []),
    { id: 'story', label: 'Story idea', icon: BookOpen },
    { id: 'play', label: 'Play style', icon: Swords },
    { id: 'look', label: 'Look & tone', icon: Palette },
  ]
  const groups: WorkbenchNavGroup[] = [{ title: 'Adventure', items: basics }]
  if (mode.value === 'advanced') {
    groups.push({
      title: 'Details',
      items: [
        { id: 'time', label: 'Time', icon: Clock },
        { id: 'world', label: 'World size', icon: Layers },
        { id: 'media', label: 'Images & voices', icon: Image },
      ],
    })
  }
  return groups
})

function goTo(id: string): void {
  activeSection.value = id
  document.getElementById(`section-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function goBack(): void {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'portal' })
}

onMounted(state.init)
</script>

<template>
  <WorkbenchShell title="New adventure" subtitle="World-Builder" back-label="Back" :page-key="mode" @back="goBack">
    <template #nav>
      <WorkbenchNav :groups="navGroups" :active="activeSection" @select="goTo" />
    </template>

    <PageHeader
      title="Generate adventure"
      description="Describe an idea; the World-Builder creates scenes, characters, items, chapters and quests from it."
    >
      <template #actions>
        <UiSegmented :model-value="mode" :options="MODES" label="Settings shown" @update:model-value="setMode" />
        <UiButton variant="ai" :icon="Dices" :loading="isSurprising" :disabled="!hasLlmConfig" @click="surpriseMe">
          Surprise me
        </UiButton>
      </template>
    </PageHeader>

    <UiNotice v-if="isConfigLoaded && !hasLlmConfig" tone="danger" title="Language model required">
      The World-Builder needs a language model (for example Gemini, GPT, Claude or a local Ollama model).
      <template #action>
        <UiButton size="sm" @click="router.push('/admin')">Open Admin</UiButton>
      </template>
    </UiNotice>
    <UiNotice v-if="errorMsg" tone="danger">{{ errorMsg }}</UiNotice>
    <UiNotice tone="info" title="Regions come later">
      This builds one connected world in a single region. To grow it into a larger campaign, open the adventure in the
      World-Editor afterwards: on the <strong>Regions</strong> page you can rename that region, add new ones and
      generate them one by one.
    </UiNotice>

    <CoverSourceSection v-if="isCoverMode" id="section-cover" class="scroll-mt-16" />
    <StorySection id="section-story" class="scroll-mt-16" />
    <PlayStyleSection id="section-play" class="scroll-mt-16" />
    <LookSection id="section-look" class="scroll-mt-16" />
    <template v-if="mode === 'advanced'">
      <TimeSection id="section-time" class="scroll-mt-16" />
      <WorldSizeSection id="section-world" class="scroll-mt-16" />
      <MediaSection id="section-media" class="scroll-mt-16" />
    </template>
    <UiNotice v-else tone="info">
      Time, world size, images and voices adapt to your idea. Switch to <strong>Advanced</strong> to set them yourself.
    </UiNotice>

    <GenerateBar />
  </WorkbenchShell>
</template>
