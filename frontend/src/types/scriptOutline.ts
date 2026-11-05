/** One function entry in a script's outline view. */
export interface OutlineFunction {
  name: string
  params: string
  /** 1-based line number in source. */
  line: number
  /** 0-based character column. */
  column: number
  /** Nesting level / indent spaces. */
  indent: number
  isAsync: boolean
  /** Enclosing scope, e.g. class name or parent function if nested. */
  scope?: string
  docstring?: string
}
