import { ref } from 'vue'

export const isMobileSidebarOpen = ref(false)

export function openMobileSidebar() {
  isMobileSidebarOpen.value = true
}

export function closeMobileSidebar() {
  isMobileSidebarOpen.value = false
}

const GAME_HEADER_COLLAPSED_KEY = 'tw_game_header_collapsed'

function readHeaderCollapsed(): boolean {
  try {
    // Collapsed unless the player expanded it before: more room for the story.
    return localStorage.getItem(GAME_HEADER_COLLAPSED_KEY) !== 'false'
  } catch {
    return true
  }
}

/** In-game focus mode: hides the app header and the game header bar until expanded. */
export const isGameHeaderCollapsed = ref(readHeaderCollapsed())

export function toggleGameHeader() {
  isGameHeaderCollapsed.value = !isGameHeaderCollapsed.value
  try {
    localStorage.setItem(GAME_HEADER_COLLAPSED_KEY, String(isGameHeaderCollapsed.value))
  } catch {
    /* storage unavailable (private mode) */
  }
}
