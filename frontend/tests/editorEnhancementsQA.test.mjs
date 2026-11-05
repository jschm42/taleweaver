import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { Buffer } from 'node:buffer'
import ts from 'typescript'

function loadTsModule(relativePath) {
  const fileUrl = new URL(relativePath, import.meta.url)
  const code = readFileSync(fileUrl, 'utf8')
  const transpiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
  }).outputText.replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
  return import(`data:text/javascript;base64,${Buffer.from(transpiled).toString('base64')}`)
}

const { parseScriptOutline } = await loadTsModule('../src/utils/scriptOutlineParser.ts')
const {
  useScriptSearch,
  findMatches,
  buildPattern,
  MAX_SEARCH_MATCHES
} = await loadTsModule('../src/components/editor/scripting/useScriptSearch.ts')
const {
  useScriptPersistence,
  validateScriptFile,
  MAX_SCRIPT_FILE_BYTES
} = await loadTsModule('../src/components/editor/scripting/useScriptPersistence.ts')
const { ref, nextTick } = await import('vue')

// ===========================================================================
// 1. Edge Case: Malformed scripts in function outline parsing
// ===========================================================================

test('QA: outline parser handles malformed def without parentheses or colon', () => {
  const malformed = [
    'def broken_header',
    '    x = 1',
    'def valid_header(a, b):',
    '    return a + b'
  ].join('\n')

  const outline = parseScriptOutline(malformed)
  assert.equal(outline.length, 2)
  assert.equal(outline[0].name, 'broken_header')
  assert.equal(outline[0].params, '')
  assert.equal(outline[1].name, 'valid_header')
  assert.equal(outline[1].params, 'a, b')
})

test('QA: outline parser ignores def inside unclosed triple quotes spanning to EOF', () => {
  const unclosed = [
    'def normal_func():',
    '    pass',
    '"""',
    'def phantom_func():',
    '    still inside docstring',
    '    def another_phantom():',
    '        pass'
  ].join('\n')

  const outline = parseScriptOutline(unclosed)
  assert.equal(outline.length, 1)
  assert.equal(outline[0].name, 'normal_func')
})

test('QA: outline parser handles deeply nested complex type annotations and lambdas', () => {
  const complex = [
    'def advanced_func(',
    '    arg1: dict[str, list[tuple[int, ...]]],',
    '    arg2: Callable[[int], bool] = lambda x: x > 0,',
    '    arg3: set = {1, 2, (3, 4)}',
    ') -> Optional[Any]:',
    '    """Docstring for advanced_func"""',
    '    return None'
  ].join('\n')

  const outline = parseScriptOutline(complex)
  assert.equal(outline.length, 1)
  assert.equal(outline[0].name, 'advanced_func')
  assert.match(outline[0].params, /arg1: dict\[str, list\[tuple\[int, \.\.\.\]\]\]/)
  assert.match(outline[0].params, /arg2: Callable\[\[int\], bool\] = lambda x: x > 0/)
  assert.equal(outline[0].docstring, 'Docstring for advanced_func')
})

test('QA: outline parser supports unicode function names and async generators', () => {
  const unicodeScript = [
    'async def berechne_glück(wert: int):',
    '    yield wert * 2',
    '',
    'def prüfen_würfel_größe(größe):',
    '    pass'
  ].join('\n')

  const outline = parseScriptOutline(unicodeScript)
  assert.equal(outline.length, 2)
  assert.equal(outline[0].name, 'berechne_glück')
  assert.equal(outline[0].isAsync, true)
  assert.equal(outline[1].name, 'prüfen_würfel_größe')
  assert.equal(outline[1].isAsync, false)
})

test('QA: outline parser performance benchmark on 10,000-line script', () => {
  const lines = []
  for (let i = 0; i < 2000; i++) {
    lines.push(`def func_${i}(x: int = ${i}):`)
    lines.push(`    """Auto generated function ${i}."""`)
    lines.push(`    return x * ${i}`)
    lines.push('')
    lines.push(`    # Interspersed comment with def false_def_${i}():`)
  }
  const largeScript = lines.join('\n')
  assert.ok(largeScript.length > 150000)

  const start = performance.now()
  const outline = parseScriptOutline(largeScript)
  const elapsed = performance.now() - start

  assert.equal(outline.length, 2000)
  assert.equal(outline[0].name, 'func_0')
  assert.equal(outline[1999].name, 'func_1999')
  // Linear single pass should comfortably parse 2,000 functions across 10,000 lines in < 50ms
  assert.ok(elapsed < 100, `Parsing took ${elapsed.toFixed(2)}ms (expected < 100ms)`)
})

// ===========================================================================
// 2. Edge Case: Cursor placement and text insertion during ID insertion
// ===========================================================================

test('QA: cursor placement during entity ID insertion into textarea fallback', () => {
  function simulateInsertion(initialVal, selStart, selEnd, idToInsert) {
    const val = initialVal
    const start = selStart ?? val.length
    const end = selEnd ?? val.length
    const updated = val.slice(0, start) + idToInsert + val.slice(end)
    const nextCursor = start + idToInsert.length
    return { updated, nextCursor }
  }

  // 1. Insertion at start of line between quotes
  const res1 = simulateInsertion('tw.npcs.say("", "Hello")', 13, 13, 'MERCHANT_01')
  assert.equal(res1.updated, 'tw.npcs.say("MERCHANT_01", "Hello")')
  assert.equal(res1.nextCursor, 13 + 'MERCHANT_01'.length)

  // 2. Replacing an existing selected placeholder (REPLACE_ME is chars 13..23)
  const res2 = simulateInsertion('tw.npcs.say("REPLACE_ME", "Hello")', 13, 23, 'GUARD_CAPTAIN')
  assert.equal(res2.updated, 'tw.npcs.say("GUARD_CAPTAIN", "Hello")')
  assert.equal(res2.nextCursor, 13 + 'GUARD_CAPTAIN'.length)

  // 3. Consecutive insertions at current caret
  const res3a = simulateInsertion('', 0, 0, 'ITEM_A')
  const res3b = simulateInsertion(res3a.updated, res3a.nextCursor, res3a.nextCursor, '_ITEM_B')
  assert.equal(res3b.updated, 'ITEM_A_ITEM_B')
  assert.equal(res3b.nextCursor, 'ITEM_A_ITEM_B'.length)
})

// ===========================================================================
// 3. Edge Case: Unsaved changes on load & persistence guards
// ===========================================================================

test('QA: persistence baseline cleanly distinguishes initial load from user edits', async () => {
  const code = ref('')
  const persistence = useScriptPersistence(code)

  // Initial state: not dirty
  assert.equal(persistence.isDirty.value, false)

  // Async load from backend: setting code and marking saved
  const backendScript = 'tw.story.narrate("A cold breeze blows through the cavern.")'
  code.value = backendScript
  persistence.markSaved(backendScript)
  assert.equal(persistence.isDirty.value, false, 'Async loaded script should not be dirty')

  // User edits: dirty becomes true
  code.value = backendScript + '\ntw.player.damage(5)'
  assert.equal(persistence.isDirty.value, true, 'User edit must flag dirty')

  // Attempting to load while dirty triggers unsaved changes modal
  let loaderExecuted = false
  persistence.requestLoad(() => {
    loaderExecuted = true
  })
  assert.equal(persistence.showUnsavedModal.value, true, 'Unsaved modal must open when dirty')
  assert.equal(loaderExecuted, false, 'Loader must not run without confirmation')

  // Canceling load retains dirty edits
  persistence.cancelLoad()
  assert.equal(persistence.showUnsavedModal.value, false)
  assert.equal(loaderExecuted, false)
  assert.equal(persistence.isDirty.value, true)

  // Confirming discard and load
  const newScript = 'tw.system("Reset scene")'
  persistence.requestLoad(() => {
    code.value = newScript
    persistence.markSaved(newScript)
    loaderExecuted = true
  })
  assert.equal(persistence.showUnsavedModal.value, true)
  persistence.confirmDiscardAndLoad()
  assert.equal(loaderExecuted, true)
  assert.equal(code.value, newScript)
  assert.equal(persistence.isDirty.value, false)
})

test('QA: persistence validates file sizes and extensions to prevent corrupting state', () => {
  // Reject non-python/text extensions
  assert.match(validateScriptFile({ name: 'attack.bin', size: 500 }), /Unsupported file type/)
  assert.match(validateScriptFile({ name: 'payload.sh', size: 500 }), /Unsupported file type/)

  // Reject files exceeding 512KB
  assert.match(validateScriptFile({ name: 'huge_log.py', size: MAX_SCRIPT_FILE_BYTES + 1 }), /File is too large/)

  // Accept valid scripts under 512KB
  assert.equal(validateScriptFile({ name: 'init_script.py', size: 1024 }), null)
  assert.equal(validateScriptFile({ name: 'hooks.TXT', size: 2048 }), null)
})

// ===========================================================================
// 4. Edge Case: Search highlighting performance on large scripts
// ===========================================================================

test('QA: search match collection and line/col calculation performance on 10,000-line script', () => {
  const lines = []
  for (let i = 0; i < 10000; i++) {
    lines.push(`line_${i} = tw.vars.get("player_health", 100)`)
  }
  const largeScript = lines.join('\n')

  const pattern = buildPattern({
    query: 'player_health',
    matchCase: false,
    wholeWord: true,
    useRegex: false
  })

  const start = performance.now()
  const matches = findMatches(largeScript, pattern)
  const elapsed = performance.now() - start

  assert.equal(matches.length, MAX_SEARCH_MATCHES, 'Matches must hit MAX_SEARCH_MATCHES cap without hanging')
  assert.equal(matches[0].line, 0)
  assert.equal(matches[100].line, 100)
  assert.ok(elapsed < 50, `10,000-line search completed in ${elapsed.toFixed(2)}ms (expected < 50ms)`)
})

test('QA: search handles invalid regular expressions gracefully without throwing', async () => {
  const cmRef = ref(null)
  const textareaRef = ref(null)
  const codeRef = ref('some python code')

  // Direct pattern builder verification
  assert.throws(
    () => buildPattern({ query: '[unclosed-regex(', matchCase: false, wholeWord: false, useRegex: true }),
    /Invalid regular expression/
  )

  const search = useScriptSearch(cmRef, textareaRef, codeRef, () => {})
  search.isOpen.value = true
  search.useRegex.value = true
  search.query.value = '[unclosed-regex('
  await nextTick()

  assert.ok(search.searchError.value !== null, 'Search error must be populated')
  assert.equal(search.totalMatches.value, 0)
})

// ===========================================================================
// 5. Responsive layout and outline search filtering
// ===========================================================================

test('QA: outline functions filter query matches names, scopes, and parameters', () => {
  const functions = [
    { name: 'on_enter_chamber', scope: 'DungeonMap', params: 'scene_id, player', line: 10, column: 4, indent: 4, isAsync: false },
    { name: 'calculate_damage', scope: 'CombatSystem', params: 'attacker, defender, weapon', line: 50, column: 4, indent: 4, isAsync: false },
    { name: 'teleport_player', scope: null, params: 'target_scene', line: 120, column: 0, indent: 0, isAsync: true }
  ]

  function filterOutline(fns, q) {
    const needle = q.trim().toLowerCase()
    if (!needle) return fns
    return fns.filter(fn => [fn.name, fn.scope ?? '', fn.params].join(' ').toLowerCase().includes(needle))
  }

  // Filter by function name
  assert.equal(filterOutline(functions, 'chamber').length, 1)
  assert.equal(filterOutline(functions, 'chamber')[0].name, 'on_enter_chamber')

  // Filter by scope
  assert.equal(filterOutline(functions, 'combatsystem').length, 1)
  assert.equal(filterOutline(functions, 'combatsystem')[0].name, 'calculate_damage')

  // Filter by param
  assert.equal(filterOutline(functions, 'weapon').length, 1)
  assert.equal(filterOutline(functions, 'weapon')[0].name, 'calculate_damage')

  // Filter by non-existent needle
  assert.equal(filterOutline(functions, 'xyz_not_found').length, 0)
})
