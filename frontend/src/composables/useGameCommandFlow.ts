import { ref, watch, type Ref } from 'vue'
import type { Router } from 'vue-router'
import { audioService } from '@/services/audioService'
import { gameViewService } from '@/services/gameViewService'
import { gameCommandService } from '@/services/gameCommandService'

type UseGameCommandFlowOptions = {
  routeId: Ref<string>
  sheet: Ref<any>
  isActionInputBlocked: Ref<boolean>
  isCombatActive: Ref<boolean>
  disconnect: () => void
  router: Router
  sendMessage: (content: string) => Promise<void>
  showMap: Ref<boolean>
  showSheet: Ref<boolean>
  showQuests: Ref<boolean>
  addNotification: (message: string, type?: 'info' | 'success' | 'error') => void
}

export function useGameCommandFlow(options: UseGameCommandFlowOptions) {
  const {
    routeId,
    sheet,
    isActionInputBlocked,
    isCombatActive,
    disconnect,
    router,
    sendMessage,
    showMap,
    showSheet,
    showQuests,
    addNotification,
  } = options

  const showWalkthrough = ref(false)
  const showDebug = ref(false)
  const walkthroughData = ref<any | null>(null)
  const fullWorldDebug = ref<any | null>(null)
  const lastAudioErrorMessage = ref<string | null>(null)

  const goBack = () => {
    disconnect()
    router.push({ name: 'portal', query: { section: 'sessions' } })
  }

  const openDebugInspector = async () => {
    showDebug.value = true

    if (!routeId.value) {
      fullWorldDebug.value = null
      return
    }

    fullWorldDebug.value = await gameViewService.fetchFullWorldDebug(routeId.value)
  }

  const loadWalkthrough = async () => {
    if (!routeId.value) return

    walkthroughData.value = await gameViewService.fetchWalkthrough(routeId.value, sheet.value?.exp || 0)
  }

  const openWalkthroughPanel = async () => {
    await loadWalkthrough()
    showWalkthrough.value = true
  }

  const revealWalkthrough = async () => {
    await sendMessage('/walkthrough reveal')
    await loadWalkthrough()
  }

  const buyHint = async () => {
    await sendMessage('/hint')
    await loadWalkthrough()
  }

  const handlePlayerInput = async (content: string) => {
    // Unlock the AudioContext on every user send so async TTS play() is allowed.
    audioService.unlock()
    const normalized = content.trim().toLowerCase()

    const uiCommand = gameCommandService.resolveUiPanelCommand(normalized)
    if (uiCommand) {
      if (uiCommand === 'map') {
        showMap.value = true
        return
      }

      if (uiCommand === 'sheet') {
        showSheet.value = true
        return
      }

      showQuests.value = true
      return
    }

    if (isActionInputBlocked.value) {
      return
    }

    if (normalized.startsWith('/inspect')) {
      showSheet.value = false
      showMap.value = false
      showQuests.value = false
    }

    if (isCombatActive.value && !gameCommandService.isAllowedCombatCommand(content)) {
      return
    }

    const specialCommand = gameCommandService.resolveSpecialCommand(normalized)
    if (specialCommand === 'walkthrough') {
      await openWalkthroughPanel()
      return
    }

    if (specialCommand === 'walkthroughReveal') {
      await revealWalkthrough()
      showWalkthrough.value = true
      return
    }

    if (specialCommand === 'hint') {
      await buyHint()
      return
    }

    if (specialCommand === 'debugWalkthrough') {
      await sendMessage('/debug walkthrough')
      await loadWalkthrough()
      showWalkthrough.value = true
      return
    }

    if (specialCommand === 'debugRevealMap') {
      await sendMessage('/debug reveal_map')
      showMap.value = true
      return
    }

    if (specialCommand === 'debugSession') {
      await openDebugInspector()
      return
    }

    await sendMessage(content)
  }

  watch(() => audioService.lastError.value, (message) => {
    if (!message || message === lastAudioErrorMessage.value) return
    addNotification(message, 'error')
    lastAudioErrorMessage.value = message
  })

  return {
    showWalkthrough,
    showDebug,
    walkthroughData,
    fullWorldDebug,
    goBack,
    openDebugInspector,
    revealWalkthrough,
    buyHint,
    handlePlayerInput,
  }
}
