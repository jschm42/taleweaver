import DOMPurify from 'dompurify'

const FENCED_CODE_RE = /```(?:([a-zA-Z0-9_+-]+)[ \t]*)?\r?\n?([\s\S]*?)```/g
const INLINE_CODE_RE = /`([^`\r\n]+)`/g

export function escapeHtml(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Extracts fenced code blocks (``` ... ```) and inline code (`...`) before prose formatting,
 * returning tokenized text and a restore function that injects escaped <pre><code> / <code> HTML.
 */
export function extractCodePlaceholders(text: string): {
  tokenized: string
  restore: (formattedHtml: string) => string
} {
  const blocks: string[] = []
  const inlines: string[] = []

  const withoutBlocks = text.replace(FENCED_CODE_RE, (_match, _lang: string | undefined, code: string) => {
    const idx = blocks.length
    const trimmed = String(code ?? '').replace(/^\r?\n/, '').replace(/\s+$/, '')
    blocks.push(`<pre class="tw-code-block"><code>${escapeHtml(trimmed)}</code></pre>`)
    return `\uE000CODEBLOCK_${idx}\uE000`
  })

  const tokenized = withoutBlocks.replace(INLINE_CODE_RE, (_match, code: string) => {
    const idx = inlines.length
    inlines.push(`<code class="tw-inline-code">${escapeHtml(String(code ?? ''))}</code>`)
    return `\uE000INLINECODE_${idx}\uE000`
  })

  const restore = (formatted: string): string => {
    let result = formatted
      .replace(
        /(?:<span class="tw-para-break"><\/span>|<br>)*\uE000CODEBLOCK_(\d+)\uE000(?:<span class="tw-para-break"><\/span>|<br>)*/g,
        (_m, i: string) => blocks[Number(i)] ?? ''
      )
      .replace(/\uE000INLINECODE_(\d+)\uE000/g, (_m, i: string) => inlines[Number(i)] ?? '')
    return result
  }

  return { tokenized, restore }
}

/**
 * Renders choice dialog prompts and option labels with safe support for fenced code blocks,
 * inline code, **bold**, and preserved indentation / line breaks.
 */
export function renderChoiceHtml(text: string): string {
  if (!text) return ''
  const normalized = text.replace(/\r\n/g, '\n').replace(/^\n+/, '').replace(/\s+$/, '')
  if (!normalized) return ''

  const { tokenized, restore } = extractCodePlaceholders(normalized)
  const escaped = escapeHtml(tokenized)
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')

  return DOMPurify.sanitize(restore(escaped), {
    ALLOWED_TAGS: ['span', 'strong', 'em', 'br', 'div', 'pre', 'code'],
    ALLOWED_ATTR: ['class'],
  })
}

