/**
 * useGivePanel — state of the inline Give dialog (context menu "Give" on an NPC).
 *
 * The player picks inventory items and hands them to the NPC with
 * `/give_items <npc id> | A, B`; the backend moves them, fires the NPC's on_receive_item
 * trigger and lets the Game Master narrate the reaction.
 */
import { ref } from 'vue'

export interface GiveTarget {
  id: string
  name: string
  imageUrl: string | null
}

interface UseGivePanelOptions {
  /** Current scene NPCs (a getter, so the caller may define them later in setup). */
  npcs: () => any[]
  sendMessage: (command: string) => Promise<unknown>
  /** Closes the other inline prompts before the dialog opens. */
  beforeOpen: () => void
}

export function useGivePanel({ npcs, sendMessage, beforeOpen }: UseGivePanelOptions) {
  const showGivePanel = ref(false)
  const giveTarget = ref<GiveTarget | null>(null)
  const giveBusy = ref(false)

  /** Opens the dialog for the scene NPC with this id or name; false if there is none. */
  const openGivePanel = (hint: string): boolean => {
    const wanted = String(hint || '').trim().toLowerCase()
    const npc = (npcs() || []).find(
      (entry: any) => entry?.id !== 'PLAYER' && [entry?.id, entry?.name].some((v) => String(v || '').toLowerCase() === wanted)
    )
    if (!npc) {
      return false
    }
    beforeOpen()
    giveTarget.value = { id: String(npc.id), name: String(npc.name || npc.id), imageUrl: npc.image_url || null }
    showGivePanel.value = true
    return true
  }

  const closeGivePanel = (): void => {
    showGivePanel.value = false
  }

  const submitGive = async (itemIds: string[]): Promise<void> => {
    if (!giveTarget.value || !itemIds.length || giveBusy.value) {
      return
    }
    giveBusy.value = true
    try {
      await sendMessage(`/give_items ${giveTarget.value.id} | ${itemIds.join(', ')}`)
      closeGivePanel()
    } finally {
      giveBusy.value = false
    }
  }

  return { showGivePanel, giveTarget, giveBusy, openGivePanel, closeGivePanel, submitGive }
}
