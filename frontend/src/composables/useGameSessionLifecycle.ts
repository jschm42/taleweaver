import { onBeforeUnmount, onMounted, watch, type Ref } from 'vue'
import type { Router } from 'vue-router'
import { gameViewService, type GameSettings } from '@/services/gameViewService'

type UseGameSessionLifecycleOptions = {
  routeId: Ref<string>
  status: Ref<string>
  gameSettings: Ref<GameSettings>
  router: Router
  connect: (gameId: string) => Promise<void>
  disconnect: () => void
  closePanels: () => void
}

export function useGameSessionLifecycle(options: UseGameSessionLifecycleOptions): void {
  const {
    routeId,
    status,
    gameSettings,
    router,
    connect,
    disconnect,
    closePanels,
  } = options

  const connectWithRouteFallback = async (id: string) => {
    await connect(id)
    if (status.value !== 'error') return

    const resolvedGameId = await gameViewService.ensureGameIdForRouteId(id)
    if (!resolvedGameId || resolvedGameId === id) return

    await router.replace({ name: 'game', params: { id: resolvedGameId } })
  }

  const handleGlobalKeydown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      closePanels()
    }
  }

  onMounted(() => {
    void (async () => {
      const settings = await gameViewService.fetchGameSettings()
      if (settings) {
        gameSettings.value = settings
      }
    })()

    if (routeId.value) {
      void connectWithRouteFallback(routeId.value)
    }

    window.addEventListener('keydown', handleGlobalKeydown)
  })

  watch(() => routeId.value, (newId) => {
    disconnect()
    if (newId) {
      void connectWithRouteFallback(newId)
    }
  })

  onBeforeUnmount(() => {
    disconnect()
    window.removeEventListener('keydown', handleGlobalKeydown)
  })
}
