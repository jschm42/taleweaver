#!/usr/bin/env node
/* eslint-env node */
/**
 * Workbench UI convention check (docs/specs/workbench_ui.md, .claude/rules/frontend-ui.md).
 *
 * Scans the folders that are already migrated to the Workbench design system and reports
 * styling that bypasses the tokens: arbitrary font sizes and colors, raw Tailwind palette
 * colors, hex colors, `font-black`, custom letter spacing and off-scale radii.
 * Native browser dialogs are checked frontend-wide by eslint (`no-alert`).
 *
 * Add a folder to MIGRATED once it is migrated, so it cannot regress.
 * Usage: node scripts/check_workbench_ui.mjs [file-or-folder ...]
 * Exit code: number of findings (0 = clean).
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)))

export const MIGRATED = [
  'src/components/ui',
  'src/components/workbench',
  'src/views/dev',
  'src/components/admin',
  'src/views/AdminView.vue',
  // Shared fields of admin and setup wizard
  'src/components/common/ModelCombobox.vue',
  'src/components/common/OpenAICompatibleTtsFields.vue',
  'src/components/common/BrowserVoiceFields.vue',
  'src/components/common/ElevenLabsVoiceField.vue',
]

const PALETTE =
  'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose'

export const RULES = [
  {
    id: 'arbitrary-text',
    pattern: /\btext-\[[^\]]+\]/g,
    message: 'Arbitrary text size or color; use a wb-* type class or a wb-* color.',
  },
  {
    id: 'arbitrary-color',
    pattern: /\b(?:bg|border|ring|from|via|to|fill|stroke|shadow|outline|divide)-\[(?:#|rgb|hsl)[^\]]*\]/g,
    message: 'Arbitrary color; use a wb-* token.',
  },
  {
    id: 'palette-color',
    pattern: new RegExp(
      `\\b(?:bg|text|border|ring|ring-offset|from|via|to|fill|stroke|shadow|outline|divide|placeholder|accent|caret|decoration)-(?:${PALETTE})-\\d{2,3}\\b`,
      'g',
    ),
    message: 'Raw Tailwind palette color; use a semantic wb-* color.',
  },
  {
    id: 'hex-color',
    pattern: /(?<![\w&])#[0-9a-fA-F]{3,8}\b/g,
    message: 'Hex color; add or use a token in src/assets/workbench.css.',
  },
  { id: 'font-black', pattern: /\bfont-black\b/g, message: 'font-black is not part of the type scale.' },
  {
    id: 'tracking',
    pattern: /\btracking-(?:\[[^\]]+\]|widest|wider|wide|tighter|tight)\b/g,
    message: 'Custom letter spacing; only wb-overline is spaced.',
  },
  {
    id: 'radius',
    pattern: /\brounded(?:-(?:t|b|l|r|tl|tr|bl|br))?-(?:sm|lg|2xl|3xl|\[[^\]]+\])\b/g,
    message: 'Off-scale radius; use rounded-md (controls) or rounded-xl (cards, dialogs).',
  },
]

function collectFiles(target) {
  const stat = statSync(target, { throwIfNoEntry: false })
  if (!stat) {
    return []
  }
  if (stat.isFile()) {
    return /\.(vue|ts|css)$/.test(target) ? [target] : []
  }
  return readdirSync(target).flatMap((name) => collectFiles(join(target, name)))
}

/** Returns the findings of one file's text. */
export function checkText(text) {
  const findings = []
  const lines = text.split(/\r?\n/)
  lines.forEach((line, index) => {
    if (line.includes('workbench-ui-ignore')) {
      return
    }
    for (const rule of RULES) {
      for (const match of line.matchAll(rule.pattern)) {
        findings.push({ line: index + 1, rule: rule.id, match: match[0], message: rule.message })
      }
    }
  })
  return findings
}

function main(args) {
  const targets = (args.length ? args : MIGRATED).map((target) => resolve(ROOT, target))
  let total = 0
  for (const file of targets.flatMap(collectFiles)) {
    for (const finding of checkText(readFileSync(file, 'utf8'))) {
      total += 1
      const where = `${relative(ROOT, file).replaceAll('\\', '/')}:${finding.line}`
      console.log(`${where}  [${finding.rule}] ${finding.match}  ${finding.message}`)
    }
  }
  console.log(total === 0 ? 'Workbench UI check: clean.' : `Workbench UI check: ${total} finding(s).`)
  return total
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = Math.min(main(process.argv.slice(2)), 255)
}
