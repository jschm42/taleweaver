/** Shapes of the NPC memory / conversation blocks of /session-debug (session_debug_npc_social.py). */

export interface DebugMemoryFact {
  key: string
  text: string
  /** Picked up by gossip ("Heard from <name>: ..."). */
  hearsay?: boolean
}

export interface DebugNpcGossip {
  told: { to: string; key: string }[]
  heard: { from: string; key: string }[]
}

export interface DebugGossipLogEntry {
  teller: string
  listener: string
  key: string
  scene_id: string
  minute: number
}

export interface DebugNpcRelation {
  npc_id: string
  name: string
  kind: string
  note: string
  changed_by_script: boolean
}

export interface DebugConversationTopic {
  id: string
  topic: string
  with_npc_id: string
  must_convey: string
  guard_expression: string
  repeatable: boolean
  heard: boolean
}

export interface DebugNpcSocial {
  memory?: { slots: number; facts: DebugMemoryFact[] }
  gossip?: DebugNpcGossip
  conversations?: { chatty: boolean; relations: DebugNpcRelation[]; topics: DebugConversationTopic[] }
}

export interface DebugConversationSession {
  chatter: string
  gossip: boolean
  player_enabled: boolean
  scene: string
  quiet: number
  last_pair: string[]
  pending_beat: string
  heard: string[]
  gossip_log?: DebugGossipLogEntry[]
}
