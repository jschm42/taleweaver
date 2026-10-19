import { configState } from '@/store/config'
import { audioService } from '@/services/audioService'

export interface StoryBubbleAudioContext {
  sheet?: any
  gameId?: string
  currentSceneDescription?: string | null
  npcMetadata: Record<string, any>
}

/** TTS playback for story feed bubbles (narration, dialogue, system messages). */
export function useStoryBubbleAudio(getContext: () => StoryBubbleAudioContext) {
  function getBubbleTtsText(text: string, speakerName?: string) {
    return speakerName ? `${speakerName}: ${text}` : text
  }

  function isSpeakingBubble(text: string, speakerName?: string) {
    if (!audioService.isPlaying.value) return false
    const target = getBubbleTtsText(text, speakerName)
    return audioService.currentText.value === target || audioService.currentText.value === text
  }

  function speakBubble(text: string, speakerName?: string) {
    if (!text || !configState.isTtsEnabled) return
    if (isSpeakingBubble(text, speakerName)) {
      audioService.stop()
      return
    }
    const context = getContext()
    audioService.unlock()
    audioService.speak(getBubbleTtsText(text, speakerName), {
      sceneDescription: context.currentSceneDescription || undefined,
      adventureId: context.sheet?.template_id,
      sessionId: context.gameId,
      title: context.sheet?.adventure_title,
      sceneName: context.sheet?.current_scene,
      tone: context.sheet?.adventure_tone,
      npcMetadata: context.npcMetadata,
    })
  }

  return { isSpeakingBubble, speakBubble }
}
