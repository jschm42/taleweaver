/**
 * Builds the editor's trigger overview: one tree of every place that can hold a script,
 * text or guard (global, protagonist, sequences, scenes with their exits, NPCs, items),
 * with the configured triggers as leaves.
 *
 * Global and sequence scripts that target an entity are also listed under that entity as
 * "linked" leaves, so everything that reacts to e.g. the bomb shows up in one place.
 */

export type TriggerOwnerKind = 'global' | 'protagonist' | 'sequence' | 'scene' | 'exit' | 'npc' | 'object'
export type TriggerLeafKind = 'script' | 'text' | 'guard' | 'soft_rule' | 'scoped_script' | 'linked'

export interface TriggerLeaf {
  key: string
  label: string
  kind: TriggerLeafKind
  code: string
  /** Extra context shown with the code, e.g. a soft rule's condition or a script's scope. */
  note?: string
  /** For linked leaves: where the script is defined (opened by "Edit"). */
  source?: { kind: TriggerOwnerKind; id?: string; label: string }
}

export interface TriggerTreeNode {
  key: string
  label: string
  kind: TriggerOwnerKind | 'group'
  /** Entity / sequence id used to open the matching editor. */
  id?: string
  subtitle?: string
  children: TriggerTreeNode[]
  leaves: TriggerLeaf[]
}

export interface TriggerTreeInput {
  adventure?: any
  protagonist?: any
  scenes?: any[]
  exits?: any[]
  npcs?: any[]
  objects?: any[]
}

type FieldSpec = readonly [field: string, label: string, kind: TriggerLeafKind]

const SCRIPT_TEXT = (base: string, label: string): FieldSpec[] => [
  [`${base}_script`, `${label} · script`, 'script'],
  [`${base}_text`, `${label} · text`, 'text'],
]

const SCENE_FIELDS: FieldSpec[] = [
  ...SCRIPT_TEXT('on_enter_scene', 'On enter'),
  ...SCRIPT_TEXT('on_leave_scene', 'On leave'),
  ['helpers_script', 'Helpers (definitions)', 'script'],
]

const EXIT_FIELDS: FieldSpec[] = [
  ['unlock_expression', 'Unlock guard', 'guard'],
  ...SCRIPT_TEXT('on_unlock_success', 'On unlock success'),
  ...SCRIPT_TEXT('on_unlock_failure', 'On unlock failure'),
  ...SCRIPT_TEXT('on_open_exit', 'On open'),
  ...SCRIPT_TEXT('on_exit_used', 'On exit used'),
]

const NPC_FIELDS: FieldSpec[] = [
  ...SCRIPT_TEXT('on_interact', 'On interact'),
  ...SCRIPT_TEXT('on_defeat', 'On defeat'),
  ...SCRIPT_TEXT('on_protagonist_enters_scene', 'On protagonist enters'),
]

const OBJECT_FIELDS: FieldSpec[] = [
  ...SCRIPT_TEXT('on_interact', 'On interact'),
  ...SCRIPT_TEXT('on_pickup', 'On pickup'),
  ...SCRIPT_TEXT('on_drop', 'On drop'),
  ...SCRIPT_TEXT('on_equip', 'On equip'),
  ...SCRIPT_TEXT('on_unequip', 'On unequip'),
  ...SCRIPT_TEXT('on_read', 'On read'),
  ['unlock_expression', 'Unlock guard', 'guard'],
  ...SCRIPT_TEXT('on_unlock_success', 'On unlock success'),
  ...SCRIPT_TEXT('on_unlock_failure', 'On unlock failure'),
  ['craft_guard_expression', 'Craft guard', 'guard'],
  ...SCRIPT_TEXT('on_craft_success', 'On craft success'),
  ...SCRIPT_TEXT('on_craft_failure', 'On craft failure'),
  ['on_success_script', 'Switch success · script', 'script'],
  ['on_failure_script', 'Switch failure · script', 'script'],
]

const PROTAGONIST_FIELDS: FieldSpec[] = [
  ...SCRIPT_TEXT('on_hp_change', 'On HP change'),
  ...SCRIPT_TEXT('on_status_change', 'On status change'),
]

const SEQUENCE_FIELDS: FieldSpec[] = [
  ['guard_expression', 'Guard expression', 'guard'],
  ['completion_guard_expression', 'Completion guard', 'guard'],
  ...SCRIPT_TEXT('on_start_sequence', 'On start'),
  ...SCRIPT_TEXT('on_end_sequence', 'On end'),
  ['helpers_script', 'Helpers (definitions)', 'script'],
]

function asObject(value: unknown): Record<string, any> {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value as Record<string, any>
  if (typeof value !== 'string' || !value.trim()) return {}
  try {
    const parsed = JSON.parse(value)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

function asList(value: unknown): any[] {
  if (Array.isArray(value)) return value
  if (typeof value !== 'string' || !value.trim()) return []
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

/** Reads a field from the entity itself, its metadata_json or (protagonist) its stats. */
function fieldValue(source: any, field: string): string {
  const candidates = [source?.[field], asObject(source?.metadata_json)[field], asObject(source?.stats)[field]]
  const found = candidates.find((value) => typeof value === 'string' && value.trim())
  return found ? String(found).trim() : ''
}

function fieldLeaves(prefix: string, source: any, fields: FieldSpec[]): TriggerLeaf[] {
  return fields
    .map(([field, label, kind]) => ({ key: `${prefix}:${field}`, label, kind, code: fieldValue(source, field) }))
    .filter((leaf) => leaf.code)
}

function scriptLabel(script: any): string {
  const target = script?.target_id || script?.target
  const name = script?.name ? ` · ${script.name}` : ''
  return `${script?.trigger || 'script'}${target ? ` → ${target}` : ''}${name}`
}

function byName(a: TriggerTreeNode, b: TriggerTreeNode): number {
  return a.label.localeCompare(b.label)
}

interface LinkedScript {
  targetId: string
  leaf: TriggerLeaf
}

function globalNode(adventure: any, linked: LinkedScript[]): TriggerTreeNode {
  const leaves: TriggerLeaf[] = []
  const initScript = String(adventure?.init_script || '').trim()
  if (initScript) {
    leaves.push({ key: 'global:init_script', label: 'Init script', kind: 'script', code: initScript })
  }
  asList(adventure?.scripts).forEach((script: any, index: number) => {
    const code = String(script?.code || '').trim()
    if (!code) return
    const leaf: TriggerLeaf = { key: `global:script:${script?.id || index}`, label: scriptLabel(script), kind: 'script', code, note: script?.id }
    leaves.push(leaf)
    const targetId = String(script?.target_id || script?.target || '').trim()
    if (targetId) {
      linked.push({
        targetId,
        leaf: {
          ...leaf,
          key: `${leaf.key}:linked`,
          kind: 'linked',
          label: `${script.trigger} · global script ${script.id || ''}`.trim(),
          note: 'Defined in Global scripts',
          source: { kind: 'global', label: 'Global' },
        },
      })
    }
  })
  return { key: 'global', label: 'Global', kind: 'global', children: [], leaves }
}

function sequenceNode(sequence: any, linked: LinkedScript[]): TriggerTreeNode {
  const id = String(sequence?.id || '')
  const title = sequence?.title || id
  const leaves = fieldLeaves(`sequence:${id}`, sequence, SEQUENCE_FIELDS)
  asList(sequence?.soft_rules).forEach((rule: any, index: number) => {
    const guard = String(rule?.guard_expression || '').trim()
    const code = [String(rule?.script || '').trim(), String(rule?.text || '').trim() && `# text: ${rule.text}`]
      .filter(Boolean)
      .join('\n')
    leaves.push({
      key: `sequence:${id}:soft_rule:${rule?.id || index}`,
      label: `Soft rule · ${rule?.id || index + 1}`,
      kind: 'soft_rule',
      code: code || '# (no script)',
      note: `Condition: ${rule?.condition || '—'}${guard ? ` · Guard: ${guard}` : ''}${rule?.max_triggers ? ` · max ${rule.max_triggers}×` : ''}`,
    })
  })
  asList(sequence?.scripts).forEach((script: any, index: number) => {
    const code = String(script?.code || '').trim()
    if (!code) return
    const leaf: TriggerLeaf = {
      key: `sequence:${id}:script:${script?.id || index}`,
      label: scriptLabel(script),
      kind: 'scoped_script',
      code,
      note: `Only while "${title}" is active`,
    }
    leaves.push(leaf)
    const targetId = String(script?.target_id || '').trim()
    if (targetId) {
      linked.push({
        targetId,
        leaf: {
          ...leaf,
          key: `${leaf.key}:linked`,
          kind: 'linked',
          label: `${script.trigger} · sequence "${title}"`,
          note: `Defined in sequence "${title}" · only while it is active`,
          source: { kind: 'sequence', id, label: title },
        },
      })
    }
  })
  return { key: `sequence:${id}`, label: title, kind: 'sequence', id, subtitle: `#${sequence?.order ?? '?'}`, children: [], leaves }
}

function entityNode(kind: 'scene' | 'npc' | 'object', entity: any, fields: FieldSpec[]): TriggerTreeNode {
  const id = String(entity?.id || entity?.entity_id || '')
  const label = entity?.label || entity?.name || id
  const subtitle = kind === 'object' ? String(entity?.item_type || '').toUpperCase() || undefined : undefined
  return { key: `${kind}:${id}`, label, kind, id, subtitle, children: [], leaves: fieldLeaves(`${kind}:${id}`, entity, fields) }
}

function exitNode(exit: any, scenesById: Map<string, string>): TriggerTreeNode {
  const id = String(exit?.id || '')
  const target = scenesById.get(String(exit?.to_scene_id || '')) || exit?.to_scene_id || '?'
  const label = `Exit → ${target}${exit?.label ? ` (${exit.label})` : ''}`
  return { key: `exit:${id}`, label, kind: 'exit', id, children: [], leaves: fieldLeaves(`exit:${id}`, exit, EXIT_FIELDS) }
}

function attachLinked(nodes: TriggerTreeNode[], linked: LinkedScript[]): void {
  const byTarget = new Map<string, TriggerLeaf[]>()
  for (const { targetId, leaf } of linked) {
    const key = targetId.toUpperCase()
    byTarget.set(key, [...(byTarget.get(key) || []), leaf])
  }
  const visit = (node: TriggerTreeNode): void => {
    const extra = node.kind !== 'group' && node.id ? byTarget.get(node.id.toUpperCase()) : undefined
    if (extra) node.leaves.push(...extra)
    node.children.forEach(visit)
  }
  nodes.forEach(visit)
}

function group(key: string, label: string, children: TriggerTreeNode[]): TriggerTreeNode {
  return { key, label, kind: 'group', children, leaves: [] }
}

export function buildTriggerTree(input: TriggerTreeInput): TriggerTreeNode[] {
  const linked: LinkedScript[] = []
  const adventure = input.adventure || {}
  const global = globalNode(adventure, linked)

  const sequences = asList(adventure.sequences)
    .filter((s: any) => s && typeof s === 'object')
    .sort((a: any, b: any) => (Number(a.order) || 0) - (Number(b.order) || 0))
    .map((s: any) => sequenceNode(s, linked))

  const scenes = (input.scenes || []).filter((s) => s?.id)
  const scenesById = new Map(scenes.map((s) => [String(s.id), String(s.label || s.name || s.id)]))
  const sceneNodes = scenes.map((scene) => {
    const node = entityNode('scene', scene, SCENE_FIELDS)
    node.children = (input.exits || [])
      .filter((exit) => String(exit?.from_scene_id || '') === String(scene.id))
      .map((exit) => exitNode(exit, scenesById))
    return node
  }).sort(byName)

  const npcNodes = (input.npcs || []).filter((n) => n?.id).map((n) => entityNode('npc', n, NPC_FIELDS)).sort(byName)
  const objectNodes = (input.objects || []).filter((o) => o?.id).map((o) => entityNode('object', o, OBJECT_FIELDS)).sort(byName)

  const protagonist: TriggerTreeNode = {
    key: 'protagonist',
    label: input.protagonist?.name || 'Protagonist',
    kind: 'protagonist',
    children: [],
    leaves: fieldLeaves('protagonist', input.protagonist, PROTAGONIST_FIELDS),
  }

  const tree = [
    global,
    protagonist,
    group('group:sequences', 'Sequences', sequences),
    group('group:scenes', 'Scenes & Exits', sceneNodes),
    group('group:npcs', 'NPCs', npcNodes),
    group('group:objects', 'Items & Objects', objectNodes),
  ]
  attachLinked(tree, linked)
  return tree
}

/**
 * Number of leaves in the node and all its descendants. Linked leaves are references to a
 * script counted where it is defined, so they are excluded unless ``linked`` is true, which
 * counts only them.
 */
export function countLeaves(node: TriggerTreeNode, linked = false): number {
  const own = node.leaves.filter((leaf) => (leaf.kind === 'linked') === linked).length
  return own + node.children.reduce((sum, child) => sum + countLeaves(child, linked), 0)
}

/**
 * Keeps nodes that have leaves (when ``onlyConfigured``) and match ``query`` in their own label,
 * a leaf label or a leaf's code. A matching node keeps all its leaves and children.
 */
export function filterTriggerTree(nodes: TriggerTreeNode[], query: string, onlyConfigured: boolean): TriggerTreeNode[] {
  const q = query.trim().toLowerCase()
  const nodeMatches = (node: TriggerTreeNode): boolean => !q || node.label.toLowerCase().includes(q) || String(node.id || '').toLowerCase().includes(q)
  const leafMatches = (leaf: TriggerLeaf): boolean => leaf.label.toLowerCase().includes(q) || leaf.code.toLowerCase().includes(q)

  const visit = (node: TriggerTreeNode): TriggerTreeNode | null => {
    const selfMatch = nodeMatches(node) && node.kind !== 'group'
    const leaves = !q || selfMatch ? node.leaves : node.leaves.filter(leafMatches)
    const children = node.children.map(visit).filter((c): c is TriggerTreeNode => c !== null)
    const filtered = { ...node, leaves, children }
    const hasContent = leaves.length > 0 || children.length > 0
    if (node.kind === 'group') return children.length > 0 ? filtered : null
    if (onlyConfigured && !hasContent) return null
    if (q && !selfMatch && !hasContent) return null
    return filtered
  }
  return nodes.map(visit).filter((n): n is TriggerTreeNode => n !== null)
}
