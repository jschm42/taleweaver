import { computed, ref, watch, type Ref } from 'vue'
import type { ChatMessage } from '@/types'
import type { StoryTabId } from './types'
import { useUnseenCount } from './useUnseenCount'
import { getImageUrl } from '@/utils/game_icons'
import { preloadImages } from '@/utils/imagePreload'

type StoryTabsSource = {
  sceneExits: () => any[] | undefined
  items: () => any[] | undefined
  systemMessages: Ref<ChatMessage[]>
  /** Passages and Discoveries are shown in the scene sidebar instead of as tabs. */
  docked: () => boolean
}

/** Active story tab, per-tab counts and "new entries" markers for the immersive view. */
export function useStoryTabs(source: StoryTabsSource) {
  const activeStoryTab = ref<StoryTabId>('story')
  const sceneExits = computed(() => source.sceneExits() ?? [])
  const sceneItems = computed(() => source.items() ?? [])
  const systemLog = source.systemMessages
  const hasLockedExits = computed(() => sceneExits.value.some((exit: any) => exit.is_locked))

  const { unseen: unseenSystem, seenAtActivation: systemSeenAtOpen } = useUnseenCount(
    () => systemLog.value.length,
    () => activeStoryTab.value === 'system'
  )
  const { unseen: unseenItems } = useUnseenCount(
    () => sceneItems.value.length,
    () => activeStoryTab.value === 'discoveries' || source.docked()
  )

  const tabCounts = computed<Record<StoryTabId, number>>(() => ({
    story: 1,
    passages: source.docked() ? 0 : sceneExits.value.length,
    discoveries: source.docked() ? 0 : sceneItems.value.length,
    system: systemLog.value.length,
  }))

  // Discoveries thumbnails are fetched as soon as the scene's items are known, so the tab
  // opens with its pictures instead of loading them on demand.
  watch(
    sceneItems,
    (items) => {
      preloadImages(
        items.map((item: any) => (item?.image_url ? getImageUrl(item.image_url, { thumbnail: true }) : null))
      )
    },
    { immediate: true }
  )

  // A tab whose content disappeared (scene change, last item taken, moved to the sidebar) falls back to the story.
  watch(tabCounts, (counts) => {
    if (!counts[activeStoryTab.value]) {
      activeStoryTab.value = 'story'
    }
  })

  function showStory() {
    activeStoryTab.value = 'story'
  }

  return {
    activeStoryTab,
    sceneExits,
    sceneItems,
    systemLog,
    hasLockedExits,
    unseenSystem,
    unseenItems,
    systemSeenAtOpen,
    showStory,
  }
}
