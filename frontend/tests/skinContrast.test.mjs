/**
 * Guards the readability of every dialog skin: parses the design tokens in src/skins/*.css,
 * resolves var() / color-mix() and checks the WCAG contrast of each ink on its background.
 *
 * Print the full table with: SKIN_CONTRAST_REPORT=1 node --test tests/skinContrast.test.mjs
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import process from 'node:process'

const skinDir = new URL('../src/skins/', import.meta.url)
const css = readdirSync(skinDir)
  .filter((name) => name.endsWith('.css'))
  .map((name) => readFileSync(new URL(name, skinDir), 'utf8'))
  .join('\n')
  .replace(/\/\*[\s\S]*?\*\//g, '')

const registry = readFileSync(new URL('skinRegistry.ts', skinDir), 'utf8')
const skinIds = [...registry.match(/SKIN_IDS = \[([^\]]*)\]/)[1].matchAll(/'([a-z-]+)'/g)].map((m) => m[1])

/** Body text must stay comfortable for long reading; labels and large glyphs may go lower. */
const BODY = 7
const TEXT = 4.5
const LARGE = 3

/** [ink token, background token, minimum ratio] */
const PAIRS = [
  ['--tw-narration-ink', '--tw-narration-bg', BODY],
  ['--tw-bubble-ink', '--tw-bubble-bg', BODY],
  ['--tw-strong-ink', '--tw-narration-bg', TEXT],
  ['--tw-bubble-strong-ink', '--tw-bubble-bg', TEXT],
  ['--tw-dropcap-ink', '--tw-narration-bg', LARGE],
  ['--tw-panel-ink', '--tw-panel-bg', BODY],
  ['--tw-panel-muted', '--tw-panel-bg', TEXT],
  ['--tw-card-ink', '--tw-card-bg', BODY],
  ['--tw-card-muted', '--tw-card-bg', TEXT],
  ['--tw-tab-ink', '--tw-tab-bg', TEXT],
  ['--tw-tab-active-ink', '--tw-tab-active-bg', TEXT],
  ['--tw-sysnote-ink', '--tw-sysnote-bg', TEXT],
  ['--tw-overlay-ink', '--tw-overlay-bg', BODY],
  ['--tw-overlay-muted', '--tw-overlay-bg', TEXT],
  ['--tw-overlay-highlight', '--tw-overlay-bg', TEXT],
  ['--tw-arrival-tag-ink', '--tw-arrival-tag-bg', TEXT],
  ['--tw-die-ink', '--tw-die-face', TEXT],
  ['--tw-speaker-ink', '--tw-speaker-bg', TEXT],
  ['--tw-speaker-player-ink', '--tw-speaker-player-bg', TEXT],
  ['--tw-speaker-target-ink', '--tw-speaker-target-bg', TEXT],
  ['--tw-voice-tag-ink', '--tw-voice-tag-bg', TEXT],
  ['--tw-narration-tag-ink', '--tw-narration-tag-bg', TEXT],
  ['--tw-label-ink', '--tw-label-bg', TEXT],
]

/** Tags and labels without a background of their own sit on the surface that holds them. */
const SURFACE_OF = {
  '--tw-label-bg': '--tw-narration-bg',
  '--tw-narration-tag-bg': '--tw-narration-bg',
  '--tw-voice-tag-bg': '--tw-bubble-bg',
  '--tw-speaker-bg': '--tw-bubble-bg',
  '--tw-speaker-player-bg': '--tw-bubble-bg',
  '--tw-speaker-target-bg': '--tw-bubble-bg',
}

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function tokensOf(selector) {
  const tokens = {}
  const escaped = escapeRegex(selector)
  const blocks = css.matchAll(new RegExp(`(?<=^|[};])\\s*${escaped}\\s*\\{([^}]*)\\}`, 'g'))
  for (const [, body] of blocks) {
    for (const [, name, value] of body.matchAll(/(--tw-[a-z-]+)\s*:\s*([^;]+);/g)) {
      tokens[name] = value.replace(/\s+/g, ' ').trim()
    }
  }
  return tokens
}

function resolveVars(value, tokens, depth = 0) {
  if (depth > 12 || !value.includes('var(')) {
    return value
  }
  const next = value.replace(/var\((--tw-[a-z-]+)(?:,\s*([^()]*))?\)/g, (_, name, fallback) => tokens[name] ?? fallback ?? 'transparent')
  return resolveVars(next, tokens, depth + 1)
}

function parseColor(text) {
  const value = text.trim()
  if (value === 'transparent') {
    return [0, 0, 0, 0]
  }
  const hex = value.match(/^#([0-9a-f]{6})([0-9a-f]{2})?$/i)
  if (hex) {
    const n = parseInt(hex[1], 16)
    return [n >> 16, (n >> 8) & 255, n & 255, hex[2] ? parseInt(hex[2], 16) / 255 : 1]
  }
  const rgb = value.match(/^rgba?\(([^)]+)\)$/)
  if (rgb) {
    const parts = rgb[1].split(/[\s,/]+/).filter(Boolean).map(Number)
    return [parts[0], parts[1], parts[2], parts[3] ?? 1]
  }
  return null
}

/** color-mix(in srgb, A p%, B) with premultiplied alpha, like the browser. */
function mix(a, pct, b) {
  const wa = pct / 100
  const wb = 1 - wa
  const alpha = a[3] * wa + b[3] * wb
  if (alpha === 0) {
    return [0, 0, 0, 0]
  }
  const channel = (i) => (a[i] * a[3] * wa + b[i] * b[3] * wb) / alpha
  return [channel(0), channel(1), channel(2), alpha]
}

const COLOR = String.raw`(?:#[0-9a-fA-F]{6,8}|rgba?\([^()]*\)|transparent)`
const MIX = new RegExp(String.raw`color-mix\(in srgb,\s*(${COLOR})\s+([\d.]+)%,\s*(${COLOR})(?:\s+[\d.]+%)?\)`)

function flattenMixes(value) {
  let current = value
  for (let i = 0; i < 12 && MIX.test(current); i += 1) {
    current = current.replace(MIX, (_, a, pct, b) => {
      const [r, g, bl, al] = mix(parseColor(a), Number(pct), parseColor(b))
      return `rgba(${r.toFixed(1)}, ${g.toFixed(1)}, ${bl.toFixed(1)}, ${al.toFixed(3)})`
    })
  }
  return current
}

function colorsIn(value) {
  return [...flattenMixes(value).matchAll(new RegExp(COLOR, 'g'))].map((m) => parseColor(m[0])).filter(Boolean)
}

function over(color, backdrop) {
  const a = color[3]
  return [0, 1, 2].map((i) => color[i] * a + backdrop[i] * (1 - a))
}

function luminance(rgb) {
  const [r, g, b] = rgb.map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/**
 * Worst contrast of an ink on a background value. Translucent backgrounds sit on a scene
 * image, so they are composited over the backdrop that hurts most: a bright (dimmed) scene
 * for light ink, black for dark ink. Faint texture layers (alpha < 0.6) are ignored.
 */
function worstContrast(inkValue, bgValue) {
  const ink = colorsIn(inkValue)[0]
  if (!ink) {
    return null
  }
  const inkRgb = over(ink, [128, 128, 128])
  const backdrop = luminance(inkRgb) > 0.4 ? [150, 150, 150] : [0, 0, 0]
  const layers = colorsIn(bgValue).filter((color) => color[3] >= 0.6)
  if (!layers.length) {
    return null
  }
  return Math.min(...layers.map((layer) => contrast(inkRgb, over(layer, backdrop))))
}

const baseTokens = tokensOf('.tw-skin')
const report = []

for (const skin of skinIds) {
  test(`skin "${skin}" keeps its text readable`, () => {
    const tokens = { ...baseTokens, ...(skin === 'classic' ? {} : tokensOf(`[data-skin='${skin}']`)) }
    if (skin !== 'classic') {
      assert.ok(tokens['--tw-narration-bg'] !== baseTokens['--tw-narration-bg'], `no tokens found for ${skin}`)
    }
    const value = (name) => (tokens[name] ? resolveVars(tokens[name], tokens) : null)
    const failures = []
    for (const [inkName, bgName, minimum] of PAIRS) {
      const inkValue = value(inkName)
      if (!inkValue) {
        continue
      }
      const ratio =
        worstContrast(inkValue, value(bgName) ?? 'transparent') ??
        worstContrast(inkValue, value(SURFACE_OF[bgName] ?? bgName) ?? 'transparent')
      if (ratio === null) {
        continue
      }
      report.push(`${skin.padEnd(10)} ${inkName.padEnd(26)} on ${bgName.padEnd(26)} ${ratio.toFixed(2).padStart(6)} (min ${minimum})`)
      if (ratio < minimum) {
        failures.push(`${inkName} on ${bgName}: ${ratio.toFixed(2)} < ${minimum}`)
      }
    }
    assert.deepEqual(failures, [])
  })
}

test('every skin has a stylesheet, swatch and import', () => {
  const index = readFileSync(new URL('index.css', skinDir), 'utf8')
  for (const skin of skinIds.filter((id) => id !== 'classic')) {
    assert.ok(index.includes(`./${skin}.css`), `${skin}.css is not imported in index.css`)
    assert.ok(registry.includes(`id: '${skin}'`), `${skin} has no entry in SKINS`)
  }
  if (process.env.SKIN_CONTRAST_REPORT) {
    console.log(report.join('\n'))
  }
})
