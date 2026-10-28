import { api } from '@/composables/useApi'

const MAX_LISTED_ERRORS = 3

/**
 * Pre-flight check of the Story Idea blueprint tags.
 * Returns a user-facing error message, or null when generation may start.
 * A failed check request never blocks generation; the backend validates again.
 */
export async function findStoryBlueprintError(storyIdea: string): Promise<string | null> {
  if (!storyIdea.includes('[')) {
    return null
  }
  try {
    const result = await api.validateStoryBlueprint(storyIdea)
    if (!result.errors.length) {
      return null
    }
    const listed = result.errors
      .slice(0, MAX_LISTED_ERRORS)
      .map((issue) => `line ${issue.line}: ${issue.message}`)
      .join(' • ')
    const more = result.errors.length > MAX_LISTED_ERRORS ? ` (+${result.errors.length - MAX_LISTED_ERRORS} more)` : ''
    return `Story Idea blueprint has errors - ${listed}${more}`
  } catch (error) {
    console.error('Blueprint validation failed:', error)
    return null
  }
}
