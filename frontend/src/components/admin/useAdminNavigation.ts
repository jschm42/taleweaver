/**
 * Pages and sidebar groups of the admin console. The open page lives in the URL
 * (`?section=llm`), so it survives a reload and can be linked.
 */
import { computed, type ComputedRef, type WritableComputedRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AudioLines, Bot, Brain, Feather, Image, KeyRound, Mic, Music, Palette, ScrollText,
  Users, UsersRound,
} from 'lucide-vue-next'
import type { WorkbenchNavGroup } from '@/components/workbench/WorkbenchNav.vue'
import { settingsService } from '@/services/settingsService'
import { userService } from '@/services/userService'
import { catalogService } from '@/services/catalogService'

export type AdminSection =
  | 'keys' | 'llm' | 'play-agent' | 't2i' | 'tts' | 'voice-map' | 'stt' | 'audio' | 'styles' | 'tones' | 'voices' | 'users'

const SECTIONS: AdminSection[] = ['keys', 'llm', 'play-agent', 't2i', 'tts', 'voice-map', 'stt', 'audio', 'styles', 'tones', 'voices', 'users']

export interface AdminNavigation {
  activeSection: WritableComputedRef<AdminSection>
  navGroups: ComputedRef<WorkbenchNavGroup[]>
  hasNoProviderKey: ComputedRef<boolean>
  select: (id: string) => void
}

export function useAdminNavigation(): AdminNavigation {
  const route = useRoute()
  const router = useRouter()

  const activeSection = computed<AdminSection>({
    get: () => {
      const requested = String(route.query.section ?? '')
      return (SECTIONS as string[]).includes(requested) ? (requested as AdminSection) : 'keys'
    },
    set: (section) => {
      void router.replace({ query: { ...route.query, section } })
    },
  })

  const hasNoProviderKey = computed(
    () => Object.keys(settingsService.configuredKeys.value).length === 0 && !settingsService.isHydratingSettings.value,
  )

  const navGroups = computed<WorkbenchNavGroup[]>(() => [
    {
      title: 'Providers',
      items: [
        {
          id: 'keys',
          label: 'API keys',
          icon: KeyRound,
          badge: hasNoProviderKey.value ? 'missing' : null,
          badgeTone: 'warn',
        },
      ],
    },
    {
      title: 'AI models',
      items: [
        { id: 'llm', label: 'Intelligence', icon: Brain },
        { id: 'play-agent', label: 'Play-Agent', icon: Bot },
      ],
    },
    {
      title: 'Media',
      items: [
        { id: 't2i', label: 'Images', icon: Image },
        { id: 'audio', label: 'Music & audio', icon: Music },
      ],
    },
    {
      title: 'Voice',
      items: [
        { id: 'tts', label: 'Text-to-speech', icon: AudioLines },
        { id: 'voice-map', label: 'Character voices', icon: UsersRound },
        { id: 'stt', label: 'Speech-to-text', icon: Mic },
      ],
    },
    {
      title: 'Catalogs',
      items: [
        { id: 'styles', label: 'Image styles', icon: Palette, badge: catalogService.imageStylesCatalog.value.length },
        { id: 'tones', label: 'Narrative tones', icon: Feather, badge: catalogService.toneCatalog.value.length },
        { id: 'voices', label: 'Narrator personas', icon: ScrollText },
      ],
    },
    {
      title: 'System',
      items: [
        { id: 'users', label: 'Users', icon: Users, badge: userService.usersList.value.length },
      ],
    },
  ])

  function select(id: string): void {
    if ((SECTIONS as string[]).includes(id)) activeSection.value = id as AdminSection
  }

  return { activeSection, navGroups, hasNoProviderKey, select }
}
