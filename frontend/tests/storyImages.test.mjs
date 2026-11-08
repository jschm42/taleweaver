import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const storyImagesTs = new URL('../src/utils/storyImages.ts', import.meta.url)

// Transpile TS file to a temporary .mjs for native ESM imports
const storyImagesJs = ts.transpileModule(readFileSync(storyImagesTs, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const tempStoryImagesFile = new URL('./__temp_storyImages.mjs', import.meta.url)

writeFileSync(tempStoryImagesFile, storyImagesJs)

let extractStoryImages, STORY_IMAGE_TAGS, STORY_IMAGE_ATTRS

try {
  const module = await import(tempStoryImagesFile.href)
  extractStoryImages = module.extractStoryImages
  STORY_IMAGE_TAGS = module.STORY_IMAGE_TAGS
  STORY_IMAGE_ATTRS = module.STORY_IMAGE_ATTRS
} finally {
  try { unlinkSync(tempStoryImagesFile) } catch {}
}

test('extractStoryImages tokenizes a captioned image and restores a figure with figcaption', () => {
  const { tokenized, restore } = extractStoryImages('Look: ![A map](/data/map.png) here.')

  assert.match(tokenized, /^Look: \S*IMAGE_0\S* here\.$/)
  assert.ok(!tokenized.includes('!['))
  assert.equal(
    restore(tokenized),
    'Look: <figure class="tw-story-image">' +
      '<img class="tw-story-image__img" src="/data/map.png" alt="A map" loading="lazy">' +
      '<figcaption class="tw-story-image__caption">A map</figcaption></figure> here.',
  )
})

test('extractStoryImages restores an uncaptioned image without figcaption', () => {
  const { tokenized, restore } = extractStoryImages('![](/data/map.png)')

  assert.match(tokenized, /^\S*IMAGE_0\S*$/)
  const html = restore(tokenized)
  assert.equal(
    html,
    '<figure class="tw-story-image">' +
      '<img class="tw-story-image__img" src="/data/map.png" alt="" loading="lazy"></figure>',
  )
  assert.ok(!html.includes('figcaption'))
})

test('extractStoryImages swallows line breaks around the image token', () => {
  const { tokenized, restore } = extractStoryImages('Before\n![Map](/data/map.png)\nAfter')

  const formatted = tokenized.replace(/\n/g, '<br>')
  const html = restore(formatted)
  assert.ok(html.startsWith('Before<figure'))
  assert.ok(html.endsWith('</figure>After'))
})

test('extractStoryImages accepts http(s) URLs', () => {
  const { tokenized, restore } = extractStoryImages('![Web](https://example.com/a.png)')

  assert.match(tokenized, /^\S*IMAGE_0\S*$/)
  assert.ok(restore(tokenized).includes('src="https://example.com/a.png"'))
})

test('extractStoryImages ignores non-data, non-http URLs', () => {
  const unsafe = [
    '![x](javascript:alert(1))',
    '![x](data:image/png;base64,AAAA)',
    '![x](images/map.png)',
    '![x](../data/map.png)',
    '![x](ftp://example.com/a.png)',
  ]

  for (const text of unsafe) {
    const { tokenized, restore } = extractStoryImages(text)
    assert.equal(tokenized, text, `Should not tokenize: ${text}`)
    assert.equal(restore(tokenized), text, `Should not restore: ${text}`)
  }
})

test('extractStoryImages escapes caption HTML', () => {
  const { tokenized, restore } = extractStoryImages('![<b>"Map"</b>](/data/map.png)')

  const html = restore(tokenized)
  assert.ok(html.includes('alt="&lt;b&gt;&quot;Map&quot;&lt;/b&gt;"'))
  assert.ok(!html.includes('<b>'))
})

test('STORY_IMAGE_TAGS and STORY_IMAGE_ATTRS list what DOMPurify must keep', () => {
  assert.deepEqual(STORY_IMAGE_TAGS, ['img', 'figure', 'figcaption'])
  assert.deepEqual(STORY_IMAGE_ATTRS, ['src', 'alt', 'loading', 'class'])
})
