/** Editor shapes of the NPC conversation fields (backend: engine/conversations/npc_fields.py). */

export const RELATION_KINDS = [
  'FRIEND',
  'FAMILY',
  'PARTNER',
  'ALLY',
  'COLLEAGUE',
  'SUPERIOR',
  'SUBORDINATE',
  'RIVAL',
  'ENEMY',
] as const

export type RelationKind = (typeof RELATION_KINDS)[number]

export interface NpcRelation {
  npc_id: string
  kind: RelationKind
  note?: string
}

export interface ConversationTopic {
  id?: string
  topic: string
  with_npc_id?: string
  must_convey?: string
  guard_expression?: string
  repeatable?: boolean
  on_heard_script?: string
  on_heard_text?: string
}

export function emptyRelation(): NpcRelation {
  return { npc_id: '', kind: 'FRIEND', note: '' }
}

export function emptyTopic(): ConversationTopic {
  return { id: '', topic: '', with_npc_id: '', must_convey: '', guard_expression: '', repeatable: false, on_heard_script: '', on_heard_text: '' }
}

/** Entries the backend would drop anyway (no target / no topic text) are left out. */
export function cleanRelations(relations: NpcRelation[] | undefined): NpcRelation[] {
  return (relations ?? []).filter((relation) => relation.npc_id && relation.kind)
}

export function cleanTopics(topics: ConversationTopic[] | undefined): ConversationTopic[] {
  return (topics ?? []).filter((topic) => (topic.topic || '').trim())
}

export interface ConversationFormFields {
  relations: NpcRelation[]
  chatty: boolean
  conversation_topics: ConversationTopic[]
}

/** Defaults of the entity form (every entity type; only NPCs show them). */
export function conversationFormDefaults(): ConversationFormFields {
  return { relations: [], chatty: true, conversation_topics: [] }
}

type ConversationSource = Partial<ConversationFormFields> | null | undefined

/** Form values of a loaded NPC (editor payload first, raw metadata as fallback). */
export function conversationFormFromNpc(npc: ConversationSource, metadata: ConversationSource): ConversationFormFields {
  const relations = npc?.relations ?? metadata?.relations ?? []
  const topics = npc?.conversation_topics ?? metadata?.conversation_topics ?? []
  return {
    relations: relations.map((relation) => ({ ...emptyRelation(), ...relation })),
    chatty: (npc?.chatty ?? metadata?.chatty) !== false,
    conversation_topics: topics.map((topic) => ({ ...emptyTopic(), ...topic })),
  }
}

/** The save payload part (cleaned lists). */
export function conversationSavePayload(data: ConversationSource): ConversationFormFields {
  return {
    relations: cleanRelations(data?.relations),
    chatty: data?.chatty !== false,
    conversation_topics: cleanTopics(data?.conversation_topics),
  }
}
