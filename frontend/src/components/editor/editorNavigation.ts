/**
 * Pages and sidebar groups of the adventure editor (docs/specs/workbench_ui.md, section 5.2).
 * Validation is not in a group: the view pins it at the bottom of the sidebar.
 */
import { computed, defineAsyncComponent, type Component, type ComputedRef } from 'vue'
import {
  Award, BookOpen, Brain, Clock, Cog, Feather, Globe2, Image, Map, MapPin, MessagesSquare, Music, Package, Palette, Scroll,
  ScrollText, ShieldCheck, Sparkles, User, Users, Workflow,
} from 'lucide-vue-next'
import type { WorkbenchNavGroup } from '@/components/workbench/WorkbenchNav.vue'
import type { EditorContext } from '@/composables/editor/editorContext'

const page = (loader: () => Promise<{ default: Component }>): Component => defineAsyncComponent(loader)

/** Page component per editor tab key. */
export const EDITOR_PAGES: Record<string, Component> = {
  world: page(() => import('@/components/editor/pages/WorldPage.vue')),
  sequences: page(() => import('@/components/editor/pages/SequencesPage.vue')),
  quest: page(() => import('@/components/editor/pages/QuestPage.vue')),
  awards: page(() => import('@/components/editor/pages/AwardsPage.vue')),
  map: page(() => import('@/components/editor/pages/MapPage.vue')),
  regions: page(() => import('@/components/editor/pages/RegionsPage.vue')),
  scenes: page(() => import('@/components/editor/pages/ScenesPage.vue')),
  inhabitants: page(() => import('@/components/editor/pages/InhabitantsPage.vue')),
  items: page(() => import('@/components/editor/pages/ItemsPage.vue')),
  protagonist: page(() => import('@/components/editor/pages/ProtagonistPage.vue')),
  scripts: page(() => import('@/components/editor/pages/ScriptsPage.vue')),
  triggers: page(() => import('@/components/editor/pages/TriggersPage.vue')),
  time: page(() => import('@/components/editor/pages/TimePage.vue')),
  memory: page(() => import('@/components/editor/pages/MemoryPage.vue')),
  conversations: page(() => import('@/components/editor/pages/ConversationsPage.vue')),
  dynamic: page(() => import('@/components/editor/pages/DynamicPage.vue')),
  visuals: page(() => import('@/components/editor/pages/VisualsPage.vue')),
  tone: page(() => import('@/components/editor/pages/TonePage.vue')),
  audio: page(() => import('@/components/editor/pages/AudioPage.vue')),
  advanced: page(() => import('@/components/editor/pages/AdvancedPage.vue')),
  validation: page(() => import('@/components/editor/pages/ValidationPage.vue')),
}

export interface EditorNavigation {
  groups: ComputedRef<WorkbenchNavGroup[]>
  validation: ComputedRef<WorkbenchNavGroup>
}

const count = (list: unknown): number | null => (Array.isArray(list) && list.length > 0 ? list.length : null)

export function useEditorNavigation(editor: EditorContext): EditorNavigation {
  const groups = computed<WorkbenchNavGroup[]>(() => [
    {
      title: 'Story',
      items: [
        { id: 'world', label: 'Overview', icon: BookOpen },
        { id: 'sequences', label: 'Chapters', icon: Scroll, badge: count(editor.adventure?.sequences) },
        { id: 'quest', label: 'Side quests', icon: MapPin },
        { id: 'awards', label: 'Awards', icon: Award },
      ],
    },
    {
      title: 'World',
      items: [
        { id: 'map', label: 'Map', icon: Map },
        { id: 'regions', label: 'Regions', icon: Globe2, badge: count(editor.debugData?.adventure?.world_sections) },
        { id: 'scenes', label: 'Scenes', icon: Image, badge: count(editor.editorScenes) },
        { id: 'inhabitants', label: 'Characters', icon: Users, badge: count(editor.editorNpcs) },
        { id: 'items', label: 'Items', icon: Package, badge: count(editor.editorAllItems) },
      ],
    },
    { title: 'Hero', items: [{ id: 'protagonist', label: 'Protagonist', icon: User }] },
    {
      title: 'Logic',
      items: [
        { id: 'scripts', label: 'Scripts', icon: ScrollText },
        { id: 'triggers', label: 'Trigger overview', icon: Workflow },
        { id: 'time', label: 'Time & pacing', icon: Clock },
        { id: 'memory', label: 'Memory', icon: Brain },
        { id: 'conversations', label: 'NPC conversations', icon: MessagesSquare },
        { id: 'dynamic', label: 'Dynamic generator', icon: Sparkles },
      ],
    },
    {
      title: 'Presentation',
      items: [
        { id: 'visuals', label: 'Visual style', icon: Palette },
        { id: 'tone', label: 'Tone', icon: Feather },
        { id: 'audio', label: 'Audio', icon: Music },
      ],
    },
    { title: 'Settings', items: [{ id: 'advanced', label: 'Advanced', icon: Cog }] },
  ])

  const validation = computed<WorkbenchNavGroup>(() => {
    const badge = editor.validationTabBadge
    const tone = !badge || badge.total <= 0 ? 'neutral' : badge.errors > 0 ? 'danger' : badge.warnings > 0 ? 'warn' : 'neutral'
    return {
      title: 'Check',
      items: [{ id: 'validation', label: 'Validation', icon: ShieldCheck, badge: editor.validationBadgeText() || null, badgeTone: tone }],
    }
  })

  return { groups, validation }
}
