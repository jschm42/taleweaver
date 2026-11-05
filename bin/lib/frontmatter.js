// Minimal YAML frontmatter reader for SKILL.md files.
// Supports the subset skills use: scalars, quoted strings, inline lists ([a, b]),
// block lists (- item) and folded/literal block scalars (> and |).

const KEY_RE = /^([A-Za-z_][\w-]*):(?:\s+(.*))?$/;
const BLOCK_SCALAR_RE = /^([>|])[+-]?$/;
const LIST_ITEM_RE = /^\s*-\s+(.*)$/;

function unquote(value) {
  const trimmed = value.trim();
  const quote = trimmed[0];
  if ((quote === '"' || quote === "'") && trimmed.endsWith(quote) && trimmed.length >= 2) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function parseInlineList(raw) {
  return raw
    .slice(1, -1)
    .split(',')
    .map(unquote)
    .filter((item) => item !== '');
}

function isIndented(line) {
  return line === '' || /^\s/.test(line);
}

function readBlockList(lines, start) {
  const items = [];
  let index = start;
  while (index < lines.length && (isIndented(lines[index]) || LIST_ITEM_RE.test(lines[index]))) {
    const match = LIST_ITEM_RE.exec(lines[index]);
    if (match) {
      items.push(unquote(match[1]));
    }
    index += 1;
  }
  return { value: items, next: index };
}

function readBlockScalar(style, lines, start) {
  const collected = [];
  let index = start;
  while (index < lines.length && isIndented(lines[index])) {
    collected.push(lines[index].trim());
    index += 1;
  }
  const separator = style === '>' ? ' ' : '\n';
  return { value: collected.join(separator).trim(), next: index };
}

function readValue(raw, lines, start) {
  if (raw === '') {
    return readBlockList(lines, start);
  }
  const block = BLOCK_SCALAR_RE.exec(raw);
  if (block) {
    return readBlockScalar(block[1], lines, start);
  }
  if (raw.startsWith('[') && raw.endsWith(']')) {
    return { value: parseInlineList(raw), next: start };
  }
  return { value: unquote(raw), next: start };
}

function parseYamlSubset(source) {
  const lines = source.split('\n');
  const data = {};
  let index = 0;
  while (index < lines.length) {
    const match = KEY_RE.exec(lines[index]);
    index += 1;
    if (!match) {
      continue;
    }
    const { value, next } = readValue((match[2] ?? '').trim(), lines, index);
    data[match[1]] = value;
    index = next;
  }
  return data;
}

/** Split a Markdown document into its frontmatter data and body. */
export function parseFrontmatter(text) {
  const normalized = text.replace(/^﻿/, '').replace(/\r\n?/g, '\n');
  const match = /^---\n([\s\S]*?)\n---(?:\n|$)/.exec(normalized);
  if (!match) {
    return { data: {}, body: normalized };
  }
  return { data: parseYamlSubset(match[1]), body: normalized.slice(match[0].length) };
}
