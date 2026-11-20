/**
 * useRecruitPanel — state of the inline Recruit dialog (context menu "Recruit" on a companion
 * NPC whose recruit mode is ITEM).
 *
 * The player offers one inventory item with `/recruit <npc id> | <item id>`; the backend
 * decides whether it is the wanted one, recruits the NPC and runs the success / failure
 * narration.
 */
import { ref } from 'vue'

export interface RecruitTarget {
  id: string
  name: string
  imageUrl: string | null
  hint: string
}

interface UseRecruitPanelOptions {
  /** Current scene NPCs (a getter, so the caller may define them later in setup). */
  npcs: () => any[]
  sendMessage: (command: string) => Promise<unknown>
  /** Closes the other inline prompts before the dialog opens. */
  beforeOpen: () => void
}

export function useRecruitPanel({ npcs, sendMessage, beforeOpen }: UseRecruitPanelOptions) {
  const showRecruitPanel = ref(false)
  const recruitTarget = ref<RecruitTarget | null>(null)
  const recruitBusy = ref(false)

  /** Opens the dialog for the scene NPC with this id; false if there is none. */
  const openRecruitPanel = (npcId: string): boolean => {
    const wanted = String(npcId || '').trim().toLowerCase()
    const npc = (npcs() || []).find((entry: any) => String(entry?.id || '').toLowerCase() === wanted)
    if (!npc) {
      return false
    }
    beforeOpen()
    recruitTarget.value = {
      id: String(npc.id),
      name: String(npc.name || npc.id),
      imageUrl: npc.image_url || null,
      hint: String(npc.recruit_hint || ''),
    }
    showRecruitPanel.value = true
    return true
  }

  const closeRecruitPanel = (): void => {
    showRecruitPanel.value = false
  }

  const submitRecruit = async (itemIds: string[]): Promise<void> => {
    if (!recruitTarget.value || !itemIds.length || recruitBusy.value) {
      return
    }
    recruitBusy.value = true
    try {
      await sendMessage(`/recruit ${recruitTarget.value.id} | ${itemIds[0]}`)
      closeRecruitPanel()
    } finally {
      recruitBusy.value = false
    }
  }

  return { showRecruitPanel, recruitTarget, recruitBusy, openRecruitPanel, closeRecruitPanel, submitRecruit }
}
