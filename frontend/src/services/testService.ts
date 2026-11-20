import { ref } from 'vue'
import { api } from '@/composables/useApi'
import { speakWithBrowser } from '@/services/browserTts'

const BROWSER_TTS_SAMPLE = 'Welcome, traveller. This is the browser voice of TaleWeaver.'

/**
 * TestService manages API connectivity and model tests:
 * - Testing LLM models
 * - Testing Text-to-Image models (vision)
 * - Testing Text-to-Speech functionality
 *
 * Test results are stored with status (loading/success/error), message,
 * and optionally image_url for vision tests or audio playback for TTS.
 */
function extractErrorMessage(err: any, defaultMsg = 'Test failed.'): string {
  if (err?.body?.message && typeof err.body.message === 'string') {
    return err.body.message
  }
  if (err?.body?.detail && typeof err.body.detail === 'string') {
    return err.body.detail
  }
  if (err?.message && typeof err.message === 'string' && err.message !== 'Failed to fetch') {
    return err.message
  }
  if (err?.message === 'Failed to fetch') {
    return 'Could not connect to TaleWeaver backend server.'
  }
  return defaultMsg
}

/** One capability check of the admin model test (`backend/core/model_capability_probe.py`). */
export interface CapabilityCheck {
  id: string
  label: string
  passed: boolean
  detail?: string
}

/** Speed rating of a model test (`backend/core/model_speed_rating.py`). */
export interface SpeedRating {
  rating: 'fast' | 'ok' | 'slow'
  seconds: number
  label: string
  note: string
}

/** OpenRouter routing of a model test (`backend/core/openrouter_route_report.py`). */
export interface RouteInfo {
  requested: string[]
  served: string
  /** Set when the configured provider could not serve the model and another one was used. */
  fallback: string
  note: string
}

/** True when the configured OpenRouter provider was not the one that answered. */
export function routeMissed(route?: RouteInfo | null): boolean {
  if (!route) return false
  if (route.fallback) return true
  const served = route.served.trim().toLowerCase()
  return Boolean(served) && route.requested.length > 0 && !route.requested.some((p) => p.trim().toLowerCase() === served)
}

class TestService {
  // ============ STATE ============
  testResults = ref<
    Record<
      string,
      {
        status: 'loading' | 'success' | 'error'
        message: string
        image_url?: string
        checks?: CapabilityCheck[]
        speed?: SpeedRating
        routing?: RouteInfo
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

      if (data.status === 'success' && data.browser) {
        // Browser speech: the server creates no audio, this browser reads the sample itself.
        await speakWithBrowser(BROWSER_TTS_SAMPLE)
        this.testResults.value['tts'] = {
          status: 'success',
          message: 'Browser voice played. Each player hears the voices of their own browser.',
        }
      } else if (data.status === 'success' && data.audio_url) {
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
      this.testResults.value['tts'] = { status: 'error', message: extractErrorMessage(err, 'TTS test failed.') }
    }
  }

  /**
   * Test an LLM model with the specified provider.
   * Returns response time if successful.
   */
  async testLlm(
    key: string,
    model: string,
    provider: string,
    ollamaUrl: string,
    openrouterProvider?: string,
    customOpenaiUrl?: string,
    customOpenaiResponseFormat?: string,
    customOpenaiTimeout?: number,
    capabilities = false,
    /** Pass to test as (`small`, `complex`, ...); defaults to `key`. Needed when `key` is only a result slot. */
    passKey?: string,
  ) {
    this.testResults.value[key] = {
      status: 'loading',
      message: capabilities ? 'Testing capabilities (several requests)...' : 'Testing connection...',
    }

    try {
      const data = await api.testLlm({
        model,
        provider,
        ollama_url: ollamaUrl,
        openrouter_provider: openrouterProvider || undefined,
        custom_openai_url: customOpenaiUrl || undefined,
        custom_openai_response_format: customOpenaiResponseFormat || undefined,
        custom_openai_timeout: customOpenaiTimeout || undefined,
        pass_key: passKey ?? key,
        capabilities,
      })

      this.testResults.value[key] = {
        status: data.status === 'success' ? 'success' : 'error',
        message: data.response_time ? `${data.message} (${data.response_time}s)` : data.message,
        checks: Array.isArray(data.checks) ? data.checks : undefined,
        speed: data.speed ?? undefined,
        routing: data.routing ?? undefined,
      }
    } catch (err) {
      console.error(`[TestService] LLM test (${key}) failed:`, err)
      this.testResults.value[key] = { status: 'error', message: extractErrorMessage(err, 'LLM connection test failed.') }
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
    minLongEdge?: number | null,
    comfyuiUrl?: string,
    comfyuiTimeout?: number,
    comfyuiWorkflow?: string
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
        comfyui_url: cleanStr(comfyuiUrl),
        comfyui_timeout: cleanNum(comfyuiTimeout),
        comfyui_workflow: cleanStr(comfyuiWorkflow),
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
      this.testResults.value[key] = { status: 'error', message: extractErrorMessage(err, 'Image generation test failed.') }
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
