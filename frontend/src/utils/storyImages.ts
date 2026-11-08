/**
 * Markdown images in story text (`![caption](url)`, emitted by `tw.image.show` and
 * `tw.image.generate`). They are swapped for placeholders before the text is escaped and
 * formatted, then restored as an image block, so caption brackets never turn into voice tags.
 */

// Only TaleWeaver assets (/data/...) and plain web URLs; no data:, javascript: or relative paths.
const STORY_IMAGE_RE = /!\[([^\]\n]*)\]\(((?:\/data\/|https?:\/\/)[^\s()<>"']+)\)/g
const IMAGE_TOKEN_RE =
  /(?:<span class="tw-para-break"><\/span>|<br>)*IMAGE_(\d+)(?:<span class="tw-para-break"><\/span>|<br>)*/g

/** Tags and attributes DOMPurify must keep for the image block. */
export const STORY_IMAGE_TAGS = ['img', 'figure', 'figcaption']
export const STORY_IMAGE_ATTRS = ['src', 'alt', 'loading', 'class']

function escapeAttr(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function imageBlockHtml(caption: string, url: string): string {
  const alt = escapeAttr(caption.trim())
  const captionHtml = alt ? `<figcaption class="tw-story-image__caption">${alt}</figcaption>` : ''
  return (
    `<figure class="tw-story-image">` +
    `<img class="tw-story-image__img" src="${escapeAttr(url)}" alt="${alt}" loading="lazy">` +
    `${captionHtml}</figure>`
  )
}

export function extractStoryImages(text: string): {
  tokenized: string
  restore: (formattedHtml: string) => string
} {
  const images: string[] = []
  const tokenized = text.replace(STORY_IMAGE_RE, (_match, caption: string, url: string) => {
    const idx = images.length
    images.push(imageBlockHtml(caption, url))
    return `IMAGE_${idx}`
  })
  // The block is its own paragraph: line breaks around it would only add empty space.
  const restore = (formatted: string): string =>
    images.length ? formatted.replace(IMAGE_TOKEN_RE, (_m, i: string) => images[Number(i)] ?? '') : formatted
  return { tokenized, restore }
}
