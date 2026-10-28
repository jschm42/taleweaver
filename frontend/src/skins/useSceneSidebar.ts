import { ref, watch } from 'vue'

const STORAGE_KEY = 'tw_scene_sidebar'

function readEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== 'false'
  } catch {
    return true
  }
}

// Shared across components: the settings dialog writes, the immersive view reads.
// On (default): wide screens show passages, discoveries and switches in a right-hand column.
// Off: they stay in the story tabs on every screen size.
const sceneSidebarEnabled = ref<boolean>(readEnabled())

watch(sceneSidebarEnabled, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, String(value))
  } catch {
    /* storage unavailable (private mode) */
  }
})

export function useSceneSidebar() {
  return { sceneSidebarEnabled }
}
