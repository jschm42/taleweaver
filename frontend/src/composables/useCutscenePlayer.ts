/**
 * useCutscenePlayer — which cut-scene the play view shows and what plays meanwhile.
 *
 * The server queues cut-scenes (chapter intro, `tw.cutscene.play`) and sends the next one as
 * `cutscene` in every snapshot. This composable shows it once: a finished showing is confirmed
 * with `POST /{game_id}/cutscene/seen` and its token is remembered, so a snapshot that was
 * already on its way does not open it again. While a cut-scene with an audio track is open,
 * `effectiveAudio` plays that track instead of the scene audio (the game audio cross-fades back
 * afterwards). Spec: docs/specs/cutscenes.md.
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import { api } from '@/composables/useApi'
import type { AudioSnapshot, Cutscene } from '@/types'

const CUTSCENE_FADE_SECONDS = 1.5

export interface CutscenePlayer {
  active: Ref<Cutscene | null>
  isActive: ComputedRef<boolean>
  effectiveAudio: ComputedRef<AudioSnapshot | null>
  finish: () => Promise<void>
}

export function useCutscenePlayer(
  serverCutscene: Ref<Cutscene | null>,
  gameId: () => string,
  audio: Ref<AudioSnapshot | null>,
): CutscenePlayer {
  const active = ref<Cutscene | null>(null)
  const seenTokens = new Set<string>()

  function open(candidate: Cutscene | null | undefined): void {
    if (active.value || !candidate?.slides?.length || seenTokens.has(candidate.token)) return
    active.value = candidate
  }

  watch(serverCutscene, open, { immediate: true })

  async function finish(): Promise<void> {
    const current = active.value
    if (!current) return
    seenTokens.add(current.token)
    active.value = null
    try {
      const result = await api.markCutsceneSeen(gameId(), current.token)
      open(result?.cutscene)
    } catch (error) {
      console.warn('[Cutscene] Could not confirm the cut-scene', error)
    }
    open(serverCutscene.value)
  }

  const effectiveAudio = computed<AudioSnapshot | null>(() => {
    const track = active.value?.audio
    const base = audio.value
    if (!track?.url) return base
    return {
      enabled: base?.enabled ?? true,
      rev: base?.rev ?? 0,
      volume: 1,
      speech_stop: base?.speech_stop,
      now: {
        id: `cutscene:${track.id}`,
        status: 'ready',
        url: track.url,
        loop: true,
        fade: CUTSCENE_FADE_SECONDS,
        source: 'script',
      },
    }
  })

  return { active, isActive: computed(() => Boolean(active.value)), effectiveAudio, finish }
}
