import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const filename = new URL('../src/utils/scriptOutlineParser.ts', import.meta.url)
const source = ts.transpileModule(readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
}).outputText
const { parseScriptOutline } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
)

const names = outline => outline.map(fn => fn.name)
const byName = (outline, name) => outline.find(fn => fn.name === name)

test('parses basic functions with name, params and position', () => {
  const outline = parseScriptOutline(
    ['def greet(name, greeting):', '    return greeting', '', 'def noop():', '    pass'].join('\n')
  )
  assert.deepEqual(names(outline), ['greet', 'noop'])
  assert.deepEqual(outline[0], {
    name: 'greet',
    params: 'name, greeting',
    line: 1,
    column: 4,
    indent: 0,
    isAsync: false
  })
  assert.equal(outline[1].params, '')
  assert.equal(outline[1].line, 4)
  assert.equal(outline[1].isAsync, false)
})

test('flags async functions and reports the name column after the keyword', () => {
  const outline = parseScriptOutline(
    'async def fetch(url):\n    return await get(url)\n\ndef sync():\n    pass'
  )
  assert.equal(outline[0].name, 'fetch')
  assert.equal(outline[0].isAsync, true)
  assert.equal(outline[0].params, 'url')
  assert.equal(outline[0].column, 10)
  assert.equal(outline[1].isAsync, false)
})

test('joins multi-line parameter lists with annotations and defaults', () => {
  const script = [
    'def configure(',
    '    name: str,',
    '    retries: int = 3,',
    '    tags: dict[str, list[int]] = {"a": [1, 2]},',
    '    label: str = "x, (y)",',
    ') -> None:',
    '    pass',
    '',
    'def after(): pass'
  ].join('\n')
  const outline = parseScriptOutline(script)
  assert.deepEqual(names(outline), ['configure', 'after'])
  assert.equal(
    outline[0].params,
    'name: str, retries: int = 3, tags: dict[str, list[int]] = {"a": [1, 2]}, label: str = "x, (y)"'
  )
  assert.equal(outline[0].line, 1)
  assert.equal(outline[1].line, 9)
})

test('assigns class and parent-function scopes and resets them on dedent', () => {
  const script = [
    'class Door:',
    '    def open(self, force=False):',
    '        def helper(x):',
    '            return x',
    '        return helper(1)',
    '',
    '    async def close(self):',
    '        pass',
    '',
    'def top_level():',
    '    pass'
  ].join('\n')
  const outline = parseScriptOutline(script)
  assert.deepEqual(names(outline), ['open', 'helper', 'close', 'top_level'])
  assert.equal(byName(outline, 'open').scope, 'Door')
  assert.equal(byName(outline, 'open').indent, 4)
  assert.equal(byName(outline, 'helper').scope, 'open')
  assert.equal(byName(outline, 'helper').indent, 8)
  assert.equal(byName(outline, 'close').scope, 'Door')
  assert.equal(byName(outline, 'close').isAsync, true)
  assert.equal(byName(outline, 'top_level').scope, undefined)
})

test('extracts single-line and multi-line docstrings', () => {
  const script = [
    'def single():',
    '    """Returns one."""',
    '    return 1',
    '',
    'def quoted():',
    "    'Plain quote doc.'",
    '',
    'def multi():',
    '    """',
    '    Summary line.',
    '',
    '    Details here.',
    '    """',
    '    return 2',
    '',
    'def inline(): """Inline doc."""',
    '',
    'def none():',
    '    return 3'
  ].join('\n')
  const outline = parseScriptOutline(script)
  assert.deepEqual(names(outline), ['single', 'quoted', 'multi', 'inline', 'none'])
  assert.equal(byName(outline, 'single').docstring, 'Returns one.')
  assert.equal(byName(outline, 'quoted').docstring, 'Plain quote doc.')
  assert.equal(byName(outline, 'multi').docstring, 'Summary line.\n\nDetails here.')
  assert.equal(byName(outline, 'inline').docstring, 'Inline doc.')
  assert.equal(byName(outline, 'none').docstring, undefined)
})

test('ignores def inside comments and triple-quoted strings', () => {
  const script = [
    '# def commented_out():',
    'x = 1  # def trailing_comment():',
    'text = """',
    'def in_string():',
    '    pass',
    '"""',
    "other = '''def in_single_triple(): '''",
    'def real():',
    '    """def in_docstring(): no"""',
    '    s = "def in_literal():"',
    '    return s'
  ].join('\n')
  const outline = parseScriptOutline(script)
  assert.deepEqual(names(outline), ['real'])
  assert.equal(outline[0].line, 8)
  assert.equal(outline[0].docstring, 'def in_docstring(): no')
})

test('captures an incomplete def at end of file', () => {
  const outline = parseScriptOutline('def ok():\n    pass\n\ndef incomplete(')
  assert.deepEqual(names(outline), ['ok', 'incomplete'])
  assert.equal(outline[1].params, '')
  assert.equal(outline[1].line, 4)

  const partial = parseScriptOutline('def partial(a, b')
  assert.deepEqual(names(partial), ['partial'])
  assert.equal(partial[0].params, 'a, b')
})

test('keeps parsing past syntax errors inside a function body', () => {
  const script = [
    'def broken(a):',
    '    x = = 1 +',
    '    if :',
    '    return )',
    '',
    'def next_one(b):',
    '    pass'
  ].join('\n')
  const outline = parseScriptOutline(script)
  assert.deepEqual(names(outline), ['broken', 'next_one'])
  assert.equal(outline[1].params, 'b')
  assert.equal(outline[1].scope, undefined)
})

test('recovers from mismatched brackets and unclosed quotes', () => {
  const unclosedParams = parseScriptOutline('def a(x, y:\n    pass\n\ndef b(z):\n    pass')
  assert.deepEqual(names(unclosedParams), ['a', 'b'])
  assert.equal(byName(unclosedParams, 'b').params, 'z')

  const openBracketInBody = parseScriptOutline('def c():\n    items = [1, 2\n\ndef d():\n    pass')
  assert.deepEqual(names(openBracketInBody), ['c', 'd'])

  const unclosedQuote = parseScriptOutline('def e():\n    s = "never closed\n\ndef f(q):\n    pass')
  assert.deepEqual(names(unclosedQuote), ['e', 'f'])
  assert.equal(byName(unclosedQuote, 'f').params, 'q')

  const unclosedDocstring = parseScriptOutline(
    'def g():\n    """Runs off the end\n    def hidden():'
  )
  assert.deepEqual(names(unclosedDocstring), ['g'])
  assert.match(unclosedDocstring[0].docstring, /^Runs off the end/)
})

test('returns an empty outline for non-string, null or empty input', () => {
  for (const input of [null, undefined, 42, {}, [], '', '   \n\n']) {
    assert.deepEqual(parseScriptOutline(input), [])
  }
})
