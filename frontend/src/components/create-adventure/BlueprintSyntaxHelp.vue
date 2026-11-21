<script setup lang="ts">
/** Short reference of the blueprint syntax, shown in an info popover next to the story idea. */
const tags = [
  '## World  style: / tone: / win: / init_script:',
  '## Protagonist: Name  hp: / inventory:',
  '## Scene: CELL — Name  decor: / on_enter:',
  '## Exit: CELL -> HALL — label  code: / key_item: / theme: / max_depth:',
  '## NPC: WARDEN — Name  in: / hp: / attack:',
  '## Item: KEY — Name  in: / type: / hidden:',
  '## Switch: LEVER — Name  states: / transition: / on_success:',
  '## Sequence: 1 — Title  goal_item: / guard:',
  '### Rule: ID — condition  max: / script:',
  '## Script: ID  trigger: / ```python ... ```',
  '## Sidequest: ID — Title / ## Award: KEY — Title',
]

const keys = [
  ['- **key**: value', 'fixed, enforced after generation'],
  ['- **key**: ~value', 'suggestion only'],
  ['- **key**: ?', 'or omitted: the AI decides'],
  ['```python ... ```', 'multi-line script (or key: |)'],
  ['@ID', 'in text links to another entity'],
]
</script>

<template>
  <div class="space-y-2">
    <p>
      Optional Markdown headings (or bracketed <code class="wb-mono text-wb-accent-text">[Kind: ID] Name</code> tags) give the
      World-Builder a blueprint. Everything you leave out is filled in by the AI (max. 15 sequences).
    </p>
    <div class="wb-mono space-y-0.5 overflow-x-auto whitespace-pre text-wb-accent-text">
      <div v-for="tag in tags" :key="tag">{{ tag }}</div>
    </div>
    <ul class="space-y-0.5">
      <li v-for="[code, meaning] in keys" :key="code">
        <code class="wb-mono text-wb-accent-text">{{ code }}</code> {{ meaning }}
      </li>
    </ul>
    <p>Scripts, guards and IDs are checked before generation starts.</p>
    <p class="wb-hint">See docs/world-builder-syntax.md for all keys and formats.</p>
  </div>
</template>
