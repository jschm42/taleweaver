/** Shared constants, presets and styles for the setup wizard pages. */

export type SetupMode = 'cloud' | 'local'

/** Each wizard page exposes `save`; it resolves false to keep the user on the page. */
export interface WizardStepHandle {
  save?: () => Promise<boolean>
}

export interface ModelPreset {
  fast: string
  story: string
}

/** Providers that run locally and need no API key. */
export const KEYLESS_PROVIDERS = new Set(['ollama', 'stable_diffusion', 'custom_openai'])

export interface KeyProvider {
  id: string
  name: string
  uses: string
}

export const KEY_PROVIDERS: KeyProvider[] = [
  { id: 'custom_openai', name: 'OpenAI-Compatible API', uses: 'Text (Optional)' },
  { id: 'openai', name: 'OpenAI', uses: 'Text · Images' },
  { id: 'anthropic', name: 'Anthropic', uses: 'Text' },
  { id: 'google', name: 'Google Gemini', uses: 'Text · Images · Voice' },
  { id: 'openrouter', name: 'OpenRouter', uses: 'Text · Images' },
  { id: 'deepseek', name: 'DeepSeek', uses: 'Text' },
  { id: 'kimi', name: 'Kimi (Moonshot)', uses: 'Text' },
  { id: 'minimax', name: 'MiniMax', uses: 'Text' },
  { id: 'black_forest_labs', name: 'Black Forest Labs', uses: 'Images' },
  { id: 'elevenlabs', name: 'ElevenLabs', uses: 'Voice' },
]

/** Recommended text models per provider: a fast one for parsing, a strong one for storytelling. */
export const LLM_PRESETS: Record<string, ModelPreset> = {
  openai: { fast: 'gpt-5.4-mini', story: 'gpt-5.4' },
  anthropic: { fast: 'claude-haiku-4-5', story: 'claude-sonnet-4-6' },
  google: { fast: 'gemini-2.5-flash', story: 'gemini-3.1-pro-preview' },
  deepseek: { fast: 'deepseek-flash', story: 'deepseek-v4-pro' },
  kimi: { fast: 'kimi-k2.5', story: 'kimi-k2.6' },
  minimax: { fast: 'MiniMax-M2.7-highspeed', story: 'MiniMax-M3' },
  openrouter: { fast: 'openai/gpt-5-mini', story: 'openai/gpt-5-chat' },
}

/** Recommended image models per provider: `fast` for items/assets, `story` for scenes. */
export const IMAGE_PRESETS: Record<string, ModelPreset> = {
  openai: { fast: 'gpt-image-1-mini', story: 'gpt-image-1.5' },
  google: { fast: 'gemini-2.5-flash-image', story: 'gemini-3.1-flash-image-preview' },
  black_forest_labs: { fast: 'flux-2-klein-4b', story: 'flux-2-pro' },
  openrouter: { fast: 'black-forest-labs/flux.2-klein-4b', story: 'google/gemini-3.1-flash-image-preview' },
  ollama: { fast: 'x/flux2-klein', story: 'x/flux2-klein' },
  stable_diffusion: { fast: 'default', story: 'default' },
}

export const TTS_MODELS: Record<string, { id: string; name: string }[]> = {
  google: [
    { id: 'gemini-3.8-flash-tts', name: 'Gemini 3.8 Flash TTS' },
    { id: 'gemini-3.8-flash-lite-tts', name: 'Gemini 3.8 Flash Lite TTS' },
  ],
  elevenlabs: [
    { id: 'eleven_v4', name: 'Eleven v4' },
    { id: 'eleven_v4_turbo', name: 'Eleven v4 Turbo' },
    { id: 'eleven_multilingual_v2', name: 'Multilingual v2' },
  ],
}

/** Returns the preset for a provider, falling back to the first/last listed models. */
export function resolvePreset(
  presets: Record<string, ModelPreset>,
  provider: string,
  available: string[],
): ModelPreset {
  const preset = presets[provider]
  if (preset) {
    return preset
  }
  return { fast: available[0] ?? '', story: available[available.length - 1] ?? '' }
}

export function needsKey(provider: string, configuredKeys: Record<string, unknown>): boolean {
  return !KEYLESS_PROVIDERS.has(provider) && !configuredKeys[provider]
}

export const wizardStyles = {
  label: 'block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2',
  input:
    'w-full bg-white/5 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/20 transition-all',
  hint: 'text-xs text-slate-500 leading-relaxed',
  error: 'text-xs font-bold text-red-400',
  success: 'text-xs font-bold text-emerald-400',
  secondaryButton:
    'px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-[10px] font-black uppercase tracking-[0.2em] text-slate-300 hover:text-white hover:bg-white/10 transition-all disabled:opacity-40',
  option: 'p-4 rounded-2xl border text-left transition-all cursor-pointer',
  optionActive: 'bg-aether-primary/10 border-aether-primary/50',
  optionIdle: 'bg-white/[0.02] border-white/10 hover:border-white/20',
}
