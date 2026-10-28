<script setup lang="ts">
const tags = [
  '[World]  win: / lose_guard: / rules:',
  '[Protagonist] Name  hp: / inventory:',
  '[Scene: CELL] Name  on_enter: |',
  '[Exit: CELL -> HALL] label  code: / key_item:',
  '[NPC: WARDEN] Name  in: / hp: / attack:',
  '[Item: KEY] Name  in: / type: / hidden:',
  '[Switch: LEVER]  states: OFF=Dark, ON / transition:',
  '[Sequence: 1] Title  goal_item: / guard:',
  '  [Rule: ID] condition  script:',
  '[Script: ID]  trigger: / code: |',
  '[Sidequest: ID] / [Award: KEY]',
]
</script>

<template>
  <div>
    <p class="mb-2">
      Optional tags give the World-Builder a blueprint. Everything you leave out is filled in by the AI
      (max. 15 sequences).
    </p>
    <div class="space-y-0.5 mb-2 font-mono text-[10px] text-cyan-400 whitespace-pre">
      <div v-for="tag in tags" :key="tag">{{ tag }}</div>
    </div>
    <ul class="mb-2 space-y-0.5 text-[11px]">
      <li><code class="text-cyan-300">key: value</code> fixed, enforced after generation</li>
      <li><code class="text-cyan-300">key: ~value</code> suggestion only</li>
      <li><code class="text-cyan-300">key: ?</code> or omitted: the AI decides</li>
      <li><code class="text-cyan-300">key: |</code> multi-line script (indented below)</li>
      <li><code class="text-cyan-300">@ID</code> in text links to another entity</li>
    </ul>
    <p class="mb-2">Scripts, guards and IDs are checked before generation starts.</p>
    <p class="text-[10px] text-slate-400 italic">See docs/world-builder-syntax.md for all keys.</p>
  </div>
</template>
