import type { PassKey } from './LlmPassCard.vue'

/**
 * Compact model-choice hints for the "?" panel of each LLM pass card on the Intelligence and
 * Play-Agent pages. The full reasoning lives in docs/model-selection.md; keep both in sync.
 */
export interface ModelGuidance {
  /** Weakest model class that still works reliably. */
  minimum: string
  /** What the pass has to get right. */
  needs: string[]
  /** What goes wrong with a model that is too weak. */
  tooWeak: string
  /** Speed and cost advice. */
  tip: string
}

export const MODEL_GUIDANCE: Record<PassKey, ModelGuidance> = {
  small: {
    minimum: 'Flash / mini class (e.g. Gemini Flash, GPT-4.1-mini, Claude Haiku) with strict JSON schema support.',
    needs: [
      'Fill a large structured schema correctly',
      'Pick exact entity IDs from a long state block',
      'Resolve references like "open it" in any language',
      'Tell actions from mere talk',
    ],
    tooWeak:
      'Missed actions (handovers, scene changes, soft rules). The guardrails revert wrong changes but cannot add missed ones, so the game seems to ignore the player. Flash-Lite / nano is borderline, ~8B open models are not reliable.',
    tip: 'Do not save here first. Thinking off (try "low" only if actions get missed). Input-heavy: compare cached input prices.',
  },
  complex: {
    minimum: 'Flash / mini class. A stronger model buys better prose, not more correctness.',
    needs: [
      'Narrate failures from rule violations, never success',
      'Stop at an open choice instead of deciding it',
      'Keep secrets (lock codes, unknown names)',
      'Persona, TTS tags and the player\'s language',
    ],
    tooWeak: 'Overrides failures, decides choices, leaks secrets; noticeably weaker prose in languages other than English.',
    tip: 'Thinking off: it streams, so time to first token counts. Compare cached input prices.',
  },
  generator: {
    minimum: 'A strong model with long context and reliable structured output.',
    needs: ['Long, strictly valid JSON manifests', 'Consistent world logic, puzzles and scripts'],
    tooWeak: 'Invalid or truncated manifests, broken references, unsolvable puzzles.',
    tip: 'Runs rarely, so speed and price matter least here.',
  },
  compression: {
    minimum: 'Small / Lite class is enough.',
    needs: ['Summarize older turns without losing facts'],
    tooWeak: 'Forgotten story facts in long games.',
    tip: 'Cheapest pass to economize on; empty uses the Pass 1 model.',
  },
  play_agent: {
    minimum: 'Flash / mini class with structured output.',
    needs: ['Pick a sensible next action from the known map, quests and inventory'],
    tooWeak: 'Loops, repeats actions, wanders without progress.',
    tip: 'Fights are played deterministically; thinking off keeps steps fast.',
  },
}
