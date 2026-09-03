import { ref, onMounted, onUnmounted, type Ref } from 'vue'

export interface UseVoiceInputOptions {
  canSendInput: Ref<boolean>
  inputText: Ref<string>
  onSend: () => void
}

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}

function bufferToWav(buffer: Float32Array, sampleRate: number): ArrayBuffer {
  const bufferLength = buffer.length
  const wavBuffer = new ArrayBuffer(44 + bufferLength * 2)
  const view = new DataView(wavBuffer)

  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + bufferLength * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, bufferLength * 2, true)

  let offset = 44
  for (let i = 0; i < buffer.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, buffer[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return wavBuffer
}

export function useVoiceInput(options: UseVoiceInputOptions) {
  const { canSendInput, inputText, onSend } = options

  const isRecording = ref(false)
  const isTranscribing = ref(false)
  const mediaStream = ref<MediaStream | null>(null)
  const audioContext = ref<AudioContext | null>(null)
  const scriptProcessor = ref<ScriptProcessorNode | null>(null)
  const leftChannel = ref<Float32Array[]>([])
  const pttKeyPressed = ref(false)
  const recordStartTime = ref<number>(0)
  const pttPrefixSay = ref(false)
  const pttKeyActiveCode = ref('')
  let globalMouseUpListener: (() => void) | null = null

  async function startVoiceRecording() {
    if (isRecording.value || !canSendInput.value) return
    try {
      leftChannel.value = []
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStream.value = stream
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      const audioCtx = new AudioCtx({ sampleRate: 16000 })
      audioContext.value = audioCtx
      const source = audioCtx.createMediaStreamSource(stream)
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      scriptProcessor.value = processor
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0)
        leftChannel.value.push(new Float32Array(inputData))
      }
      source.connect(processor)
      processor.connect(audioCtx.destination)
      isRecording.value = true
      recordStartTime.value = Date.now()
    } catch (err) {
      console.error('Failed to start recording:', err)
    }
  }

  async function stopVoiceRecording() {
    if (!isRecording.value) return
    isRecording.value = false
    if (scriptProcessor.value) {
      scriptProcessor.value.disconnect()
      scriptProcessor.value = null
    }
    if (audioContext.value) {
      void audioContext.value.close()
      audioContext.value = null
    }
    if (mediaStream.value) {
      mediaStream.value.getTracks().forEach((track) => track.stop())
      mediaStream.value = null
    }
    if (Date.now() - recordStartTime.value < 500) return

    const totalLength = leftChannel.value.reduce((acc, chunk) => acc + chunk.length, 0)
    const flattened = new Float32Array(totalLength)
    let offset = 0
    for (const chunk of leftChannel.value) {
      flattened.set(chunk, offset)
      offset += chunk.length
    }

    const wavBuffer = bufferToWav(flattened, 16000)
    const audioBlob = new Blob([wavBuffer], { type: 'audio/wav' })
    isTranscribing.value = true
    try {
      const { api } = await import('@/composables/useApi')
      const result = await api.transcribeAudio(audioBlob)
      const text = result.text.trim()
      if (text) {
        const prefix = pttPrefixSay.value ? '/say ' : ''
        if (inputText.value.trim()) {
          inputText.value = `${inputText.value.trim()} ${prefix}${text}`
        } else {
          inputText.value = `${prefix}${text}`
        }
        onSend()
      }
    } catch (err) {
      console.error('Failed to transcribe audio:', err)
    } finally {
      isTranscribing.value = false
    }
  }

  function handleMicButtonMousedown(e: MouseEvent | TouchEvent) {
    e.preventDefault()
    if (!canSendInput.value) return
    pttPrefixSay.value = (e as MouseEvent).shiftKey || false
    pttKeyActiveCode.value = ''
    void startVoiceRecording()

    globalMouseUpListener = () => {
      void stopVoiceRecording()
      if (globalMouseUpListener) {
        window.removeEventListener('mouseup', globalMouseUpListener)
        window.removeEventListener('touchend', globalMouseUpListener)
        globalMouseUpListener = null
      }
    }
    window.addEventListener('mouseup', globalMouseUpListener)
    window.addEventListener('touchend', globalMouseUpListener)
  }

  function handleGlobalKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement
    const isTyping = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable

    const isV = e.code === 'KeyV'
    const isB = e.code === 'KeyB'
    const isT = e.code === 'KeyT'
    if ((isV || isB || isT) && !isTyping && canSendInput.value) {
      e.preventDefault()
      if (!pttKeyPressed.value) {
        pttKeyPressed.value = true
        pttKeyActiveCode.value = e.code
        pttPrefixSay.value = isB || isT || e.shiftKey
        void startVoiceRecording()
      }
    }
  }

  function handleGlobalKeyup(e: KeyboardEvent) {
    const activeCode = pttKeyActiveCode.value || 'KeyV'
    if (e.code === activeCode && pttKeyPressed.value) {
      e.preventDefault()
      pttKeyPressed.value = false
      pttKeyActiveCode.value = ''
      void stopVoiceRecording()
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleGlobalKeydown, { capture: true })
    window.addEventListener('keyup', handleGlobalKeyup)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleGlobalKeydown, { capture: true })
    window.removeEventListener('keyup', handleGlobalKeyup)
    if (globalMouseUpListener) {
      window.removeEventListener('mouseup', globalMouseUpListener)
      window.removeEventListener('touchend', globalMouseUpListener)
      globalMouseUpListener = null
    }
  })

  return {
    isRecording,
    isTranscribing,
    startVoiceRecording,
    stopVoiceRecording,
    handleMicButtonMousedown,
  }
}
