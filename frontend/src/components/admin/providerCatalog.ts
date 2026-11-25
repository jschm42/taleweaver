/** Providers shown on the admin API keys page. */
export interface ProviderMeta {
  id: string
  name: string
  category: 'major' | 'specialized' | 'local'
  capabilities: string[]
  description: string
  keyPrefix?: string
  docsUrl?: string
}

export const PROVIDERS: ProviderMeta[] = [
  {
    id: 'custom_openai',
    name: 'OpenAI-Compatible LLM',
    category: 'specialized',
    capabilities: ['LLM'],
    description: 'API key for a hosted OpenAI-compatible LLM gateway or self-hosted endpoint. Optional for unauthenticated servers.',
  },
  {
    id: 'custom_openai_tts',
    name: 'OpenAI-Compatible Speech',
    category: 'specialized',
    capabilities: ['TTS'],
    description: 'API key for the OpenAI-compatible speech server (e.g. OpenAI TTS). Leave empty for local servers like Piper or Kokoro; the LLM key is never sent there.',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    category: 'major',
    capabilities: ['LLM', 'T2I', 'TTS'],
    description: 'GPT-4o, GPT-4o-mini, image generation, and TTS voices.',
    keyPrefix: 'sk-...',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'google',
    name: 'Google Gemini',
    category: 'major',
    capabilities: ['LLM', 'TTS (Gemini Voice)'],
    description: 'Gemini 2.5 Flash / Pro reasoning and high-fidelity Gemini TTS voices.',
    keyPrefix: 'AIza...',
    docsUrl: 'https://aistudio.google.com/app/apikey',
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    category: 'major',
    capabilities: ['LLM'],
    description: 'Claude 3.5 Sonnet and Haiku for deep narrative prose.',
    keyPrefix: 'sk-ant-...',
    docsUrl: 'https://console.anthropic.com/settings/keys',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    category: 'major',
    capabilities: ['LLM', 'T2I'],
    description: 'Unified gateway for hundreds of open and proprietary AI models.',
    keyPrefix: 'sk-or-...',
    docsUrl: 'https://openrouter.ai/keys',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    category: 'major',
    capabilities: ['LLM'],
    description: 'DeepSeek-V3 and DeepSeek-R1 reasoning models with high cost-efficiency.',
    keyPrefix: 'sk-...',
    docsUrl: 'https://platform.deepseek.com/api_keys',
  },
  {
    id: 'minimax',
    name: 'MiniMax',
    category: 'specialized',
    capabilities: ['LLM', 'TTS'],
    description: 'MiniMax-01 and high-capacity long-context reasoning models.',
    keyPrefix: 'eyJ...',
    docsUrl: 'https://api.minimax.chat',
  },
  {
    id: 'black_forest_labs',
    name: 'Black Forest Labs',
    category: 'specialized',
    capabilities: ['T2I (FLUX)'],
    description: 'State-of-the-art FLUX.1 & FLUX 3 visual generation models.',
    keyPrefix: 'bfl-...',
    docsUrl: 'https://docs.bfl.ml',
  },
  {
    id: 'lumigen',
    name: 'Lumigen MCP',
    category: 'specialized',
    capabilities: ['T2I (MCP)'],
    description: 'Lumigen image generation MCP server (Bearer token).',
    docsUrl: 'https://github.com/jschm42/lumigen',
  },
  {
    id: 'elevenlabs',
    name: 'ElevenLabs',
    category: 'specialized',
    capabilities: ['TTS'],
    description: 'Ultra-realistic character narration with emotional voice control.',
    keyPrefix: 'sk_...',
    docsUrl: 'https://elevenlabs.io',
  },
  {
    id: 'kimi',
    name: 'Kimi (Moonshot)',
    category: 'specialized',
    capabilities: ['LLM'],
    description: 'Moonshot AI long-context models for intricate world lore.',
    keyPrefix: 'sk-...',
    docsUrl: 'https://platform.moonshot.cn',
  },
  {
    id: 'ollama',
    name: 'Ollama',
    category: 'local',
    capabilities: ['Local LLM', 'Local T2I'],
    description: 'Self-hosted open models running entirely on your local hardware.',
  },
]
