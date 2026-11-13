<script setup lang="ts">
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
</script>

<template>
  <div>
    <p class="mb-2">
      Optional Markdown headings (or bracketed <code class="text-cyan-300">[Kind: ID] Name</code> tags) give the
      World-Builder a blueprint. Everything you leave out is filled in by the AI (max. 15 sequences).
    </p>
    <div class="space-y-0.5 mb-2 font-mono text-[10px] text-cyan-400 whitespace-pre">
      <div v-for="tag in tags" :key="tag">{{ tag }}</div>
    </div>
    <ul class="mb-2 space-y-0.5 text-[11px]">
      <li><code class="text-cyan-300">- **key**: value</code> or <code class="text-cyan-300">key: value</code> fixed, enforced after generation</li>
      <li><code class="text-cyan-300">- **key**: ~value</code> suggestion only</li>
      <li><code class="text-cyan-300">- **key**: ?</code> or omitted: the AI decides</li>
      <li><code class="text-cyan-300">```python ... ```</code> or <code class="text-cyan-300">key: |</code> multi-line script</li>
      <li><code class="text-cyan-300">@ID</code> in text links to another entity</li>
    </ul>
    <p class="mb-2">Scripts, guards and IDs are checked before generation starts.</p>
    <p class="text-[10px] text-slate-400 italic">See docs/world-builder-syntax.md for all keys and formats.</p>
  </div>
</template>
