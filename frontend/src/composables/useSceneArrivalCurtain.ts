import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'

/** How long the travel curtain stays up for a scene change the turn did not announce. */
const ARRIVAL_CURTAIN_MS = 1800

export type ArrivalTarget = {
  label: string
  targetSceneName: string
  targetSceneId: string
  targetSceneImage?: string | null
}

/**
 * Plays the travel overlay briefly when the player lands in another scene without walking
 * through an exit (e.g. `tw.scene.teleport` in a script), so every scene change looks alike.
 */
export function useSceneArrivalCurtain(
  arrival: Ref<{ sceneId: string; at: number } | null>,
  resolveSceneName: (sceneId: string) => string,
  resolveSceneImage: (sceneId: string) => string | null | undefined,
) {
  const arrivalTarget = ref<ArrivalTarget | null>(null)
  let timer: number | null = null

  const clearTimer = () => {
    if (timer !== null) window.clearTimeout(timer)
    timer = null
  }

  watch(arrival, (value) => {
    if (!value?.sceneId) return
    clearTimer()
    arrivalTarget.value = {
      label: '',
      targetSceneName: resolveSceneName(value.sceneId) || 'New Location',
      targetSceneId: value.sceneId,
      targetSceneImage: resolveSceneImage(value.sceneId),
    }
    timer = window.setTimeout(() => {
      arrivalTarget.value = null
      timer = null
    }, ARRIVAL_CURTAIN_MS)
  })

  onBeforeUnmount(clearTimer)

  return { arrivalTarget, isArriving: computed(() => arrivalTarget.value !== null) }
}
