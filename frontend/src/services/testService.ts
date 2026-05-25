import { ref } from 'vue'
import { api } from '@/composables/useApi'

/**
 * TestService manages API connectivity and model tests:
 * - Testing LLM models
 * - Testing Text-to-Image models (vision)
 * - Testing Text-to-Speech functionality
 *
 * Test results are stored with status (loading/success/error), message,
 * and optionally image_url for vision tests or audio playback for TTS.
 */
class TestService {
  // ============ STATE ============
  testResults = ref<
    Record<
      string,
      {
        status: 'loading' | 'success' | 'error'
        message: string
        image_url?: string
      }
    >
  >({})

  // ============ TEST OPERATIONS ============

  /**
   * Test Text-to-Speech functionality.
   * Generates test audio and attempts to play it.
   */
  async testTTS() {
    this.testResults.value['tts'] = { status: 'loading', message: 'Testing Speech...' }

    try {
      const data = await api.testTTS()

      if (data.status === 'success' && data.audio_url) {
        // Attempt to play the generated audio
        const audio = new Audio(data.audio_url)
        await audio.play()
        this.testResults.value['tts'] = { status: 'success', message: 'Speech generated and played!' }
      } else {
        this.testResults.value['tts'] = {
          status: 'error',
          message: data.message || 'No audio generated.',
        }
      }
    } catch (err: any) {
      console.error('[TestService] TTS test failed:', err)
      this.testResults.value['tts'] = { status: 'error', message: err.message || 'Test failed.' }
    }
  }

  /**
   * Test an LLM model with the specified provider.
   * Returns response time if successful.
   */
  async testLlm(key: string, model: string, provider: string, ollamaUrl: string) {
    this.testResults.value[key] = { status: 'loading', message: 'Testing connection...' }

    try {
      const data = await api.testLlm({ model, provider, ollama_url: ollamaUrl })

      this.testResults.value[key] = {
        status: data.status === 'success' ? 'success' : 'error',
        message: data.response_time ? `${data.message} (${data.response_time}s)` : data.message,
      }
    } catch (err) {
      console.error(`[TestService] LLM test (${key}) failed:`, err)
      this.testResults.value[key] = { status: 'error', message: 'Test failed.' }
    }
  }

  /**
   * Test a Text-to-Image model with the specified provider.
   * Generates and displays a test image.
   */
  async testVision(
    key: string,
    model: string,
    provider: string,
    ollamaUrl: string,
    stableDiffusionUrl?: string,
    steps?: number | null,
    cfgScale?: number | null,
    width?: number | null,
    height?: number | null,
    samplerName?: string | null,
    scheduler?: string | null,
    minLongEdge?: number | null
  ) {
    this.testResults.value[key] = { status: 'loading', message: 'Generating test image...' }

    const cleanNum = (val: any) => {
      if (val === null || val === undefined || val === '') return undefined
      const num = Number(val)
      return isNaN(num) ? undefined : num
    }

    const cleanStr = (val: any) => {
      if (val === null || val === undefined || String(val).trim() === '') return undefined
      return String(val).trim()
    }

    try {
      const data = await api.testVision({
        model,
        provider,
        ollama_url: cleanStr(ollamaUrl),
        stable_diffusion_url: cleanStr(stableDiffusionUrl),
        steps: cleanNum(steps),
        cfg_scale: cleanNum(cfgScale),
        sampler_name: cleanStr(samplerName),
        scheduler: cleanStr(scheduler),
        width: cleanNum(width),
        height: cleanNum(height),
        min_long_edge: cleanNum(minLongEdge)
      })

      this.testResults.value[key] = {
        status: data.status === 'success' ? 'success' : 'error',
        message: data.message,
        image_url: data.image_url,
      }
    } catch (err) {
      console.error(`[TestService] Vision test (${key}) failed:`, err)
      this.testResults.value[key] = { status: 'error', message: 'Test failed.' }
    }
  }

  /**
   * Clear test results for a specific key or all tests.
   */
  clearResults(key?: string) {
    if (key) {
      delete this.testResults.value[key]
    } else {
      this.testResults.value = {}
    }
  }
}

export const testService = new TestService()
