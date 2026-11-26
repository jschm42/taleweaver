import { apiFetch } from '@/services/http'

export type McpFeatureKey =
  | 'read_adventures'
  | 'read_sessions'
  | 'edit_adventures'
  | 'generate_adventures'
  | 'generate_media'
  | 'diagnostics'

export type McpFeatureFlags = Record<McpFeatureKey, boolean>

export interface McpSettings {
  enabled: boolean
  features: McpFeatureFlags
  allow_destructive: boolean
  allow_cross_user_access: boolean
  endpoint_path: string
}

export type McpSettingsUpdate = Omit<McpSettings, 'endpoint_path'>

export type McpTokenStatus = 'active' | 'expired' | 'revoked'

export interface McpTokenRecord {
  id: string
  name: string
  token_prefix: string
  user_id: string
  username: string
  user_role: string
  allowed_features: McpFeatureKey[] | null
  status: McpTokenStatus
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
}

export interface CreateMcpTokenPayload {
  name: string
  user_id?: string | null
  allowed_features?: McpFeatureKey[] | null
  expires_in_days?: number | null
}

export interface McpTokenCreated {
  token: McpTokenRecord
  plain_token: string
}

export interface McpFeatureMeta {
  key: McpFeatureKey
  label: string
  description: string
  quotaLabel?: string
  quotaTone?: 'ai' | 'warn'
  readOnlyDefault?: boolean
}

export const MCP_FEATURE_META: McpFeatureMeta[] = [
  {
    key: 'read_adventures',
    label: 'Library & adventure read',
    description:
      'List and inspect adventures, manifests, catalogs, change-set schemas, and live TaleWeaver docs.',
    readOnlyDefault: true,
  },
  {
    key: 'read_sessions',
    label: 'Session inspection',
    description:
      'List game sessions and inspect runtime state, inventories, checkpoints, and player chat logs.',
    readOnlyDefault: true,
  },
  {
    key: 'edit_adventures',
    label: 'Adventure editing & import',
    description:
      'Validate blueprints and templates, apply change sets (dry-run or commit), manage cutscenes/audio tracks, and import manifests.',
  },
  {
    key: 'generate_adventures',
    label: 'Adventure & region generation',
    description:
      'Run World-Builder LLM generation, Region Builder, story suggestions, and AI validation/fixes.',
    quotaLabel: 'LLM quota',
    quotaTone: 'ai',
  },
  {
    key: 'generate_media',
    label: 'Visuals & audio rendering',
    description:
      'Generate or upload adventure images via MediaEngine, render audio tracks, and regenerate thumbnails.',
    quotaLabel: 'Media quota',
    quotaTone: 'warn',
  },
  {
    key: 'diagnostics',
    label: 'System diagnostics & telemetry',
    description: 'Inspect database health, storage usage, and LLM pipeline latency benchmarks.',
    readOnlyDefault: true,
  },
]

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const mcpSettingsService = {
  async load(): Promise<McpSettings> {
    return readJson<McpSettings>(await apiFetch('/settings/mcp'))
  },

  async save(values: McpSettingsUpdate): Promise<McpSettings> {
    const res = await apiFetch('/settings/mcp', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify(values),
    })
    return readJson<McpSettings>(res)
  },

  async listTokens(): Promise<McpTokenRecord[]> {
    return readJson<McpTokenRecord[]>(await apiFetch('/settings/mcp/tokens'))
  },

  async createToken(payload: CreateMcpTokenPayload): Promise<McpTokenCreated> {
    const res = await apiFetch('/settings/mcp/tokens', {
      method: 'POST',
      includeJson: true,
      body: JSON.stringify(payload),
    })
    return readJson<McpTokenCreated>(res)
  },

  async revokeToken(tokenId: string): Promise<McpTokenRecord> {
    const res = await apiFetch(`/settings/mcp/tokens/${encodeURIComponent(tokenId)}`, {
      method: 'DELETE',
    })
    return readJson<McpTokenRecord>(res)
  },
}
