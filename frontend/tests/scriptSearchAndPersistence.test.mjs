import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

function loadTsModule(relativePath) {
  const fileUrl = new URL(relativePath, import.meta.url)
  const code = readFileSync(fileUrl, 'utf8')
  const transpiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
  }).outputText.replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
  return import(`data:text/javascript;base64,${Buffer.from(transpiled).toString('base64')}`)
}

test('script persistence file validation and limits', async () => {
  const { MAX_SCRIPT_FILE_BYTES, validateScriptFile } = await loadTsModule(
    '../src/components/editor/scripting/useScriptPersistence.ts'
  )
  assert.equal(MAX_SCRIPT_FILE_BYTES, 512 * 1024)

  // Valid extensions
  assert.equal(validateScriptFile({ name: 'quest.py', size: 1024 }), null)
  assert.equal(validateScriptFile({ name: 'dialogue.TXT', size: 2048 }), null)

  // Invalid extensions
  assert.match(validateScriptFile({ name: 'script.exe', size: 100 }), /Unsupported file type/)
  assert.match(validateScriptFile({ name: 'data.json', size: 100 }), /Unsupported file type/)

  // Size limit exceeded
  assert.match(
    validateScriptFile({ name: 'huge.py', size: MAX_SCRIPT_FILE_BYTES + 1 }),
    /File is too large/
  )
})

test('script search pattern builder', async () => {
  const { buildPattern } = await loadTsModule('../src/components/editor/scripting/useScriptSearch.ts')

  // Normal text search
  const pat1 = buildPattern({ query: 'tw.vars', matchCase: false, wholeWord: false, useRegex: false })
  assert.equal(pat1.test('tw.vars.set("gold", 10)'), true)
  pat1.lastIndex = 0
  assert.equal(pat1.test('TW.VARS.set("gold", 10)'), true)

  // Case sensitive
  const pat2 = buildPattern({ query: 'tw.vars', matchCase: true, wholeWord: false, useRegex: false })
  assert.equal(pat2.test('tw.vars.set("gold", 10)'), true)
  assert.equal(pat2.test('TW.VARS.set("gold", 10)'), false)

  // Whole word
  const pat3 = buildPattern({ query: 'gold', matchCase: false, wholeWord: true, useRegex: false })
  assert.equal(pat3.test('player has gold here'), true)
  assert.equal(pat3.test('player has golden coin'), false)

  // Custom regex
  const pat4 = buildPattern({ query: 'tw\\.[a-z]+', matchCase: false, wholeWord: false, useRegex: true })
  assert.equal(pat4.test('tw.scene.id'), true)
  assert.equal(pat4.test('other.scene.id'), false)
})

test('script search match finding and line/col calculation', async () => {
  const { buildPattern, findMatches } = await loadTsModule(
    '../src/components/editor/scripting/useScriptSearch.ts'
  )

  const text = 'line 1: tw.narrate("Hello")\nline 2: tw.narrate("World")\nline 3: end'
  const pattern = buildPattern({ query: 'tw.narrate', matchCase: false, wholeWord: false, useRegex: false })
  const matches = findMatches(text, pattern)

  assert.equal(matches.length, 2)
  assert.equal(matches[0].line, 0)
  assert.equal(matches[0].ch, 8)
  assert.equal(matches[1].line, 1)
  assert.equal(matches[1].ch, 8)
})

test('useScriptSearch reactive search, replace, and navigation', async () => {
  const { ref, nextTick } = await import('vue')
  const { useScriptSearch } = await loadTsModule(
    '../src/components/editor/scripting/useScriptSearch.ts'
  )

  const code = ref('tw.narrate("foo")\ntw.narrate("bar")\ntw.narrate("baz")')
  const onCodeChange = (newVal) => { code.value = newVal }

  const search = useScriptSearch(
    ref(null),
    ref(null),
    code,
    onCodeChange
  )

  // Open search and query
  search.openSearch()
  search.query.value = 'tw.narrate'
  search.replaceText.value = 'tw.echo'
  await nextTick()

  assert.equal(search.totalMatches.value, 3)
  assert.equal(search.currentMatchIndex.value, 0)

  // Navigate next and previous
  search.findNext()
  assert.equal(search.currentMatchIndex.value, 1)
  search.findNext()
  assert.equal(search.currentMatchIndex.value, 2)
  search.findNext()
  assert.equal(search.currentMatchIndex.value, 0) // wraps around
  search.findPrev()
  assert.equal(search.currentMatchIndex.value, 2)

  // Replace all
  search.replaceAll()
  await nextTick()
  assert.equal(code.value, 'tw.echo("foo")\ntw.echo("bar")\ntw.echo("baz")')
})

test('useScriptPersistence dirty tracking and unsaved changes guard', async () => {
  const { ref } = await import('vue')
  const { useScriptPersistence } = await loadTsModule(
    '../src/components/editor/scripting/useScriptPersistence.ts'
  )

  const code = ref('print("hello")')
  const persistence = useScriptPersistence(code)

  // Initially not dirty
  assert.equal(persistence.isDirty.value, false)

  // Edit code -> dirty
  code.value = 'print("hello world")'
  assert.equal(persistence.isDirty.value, true)

  // Mark saved -> clean
  persistence.markSaved('print("hello world")')
  assert.equal(persistence.isDirty.value, false)

  // Request load when dirty guards with modal
  code.value = 'print("unsaved change")'
  assert.equal(persistence.isDirty.value, true)

  let loaded = false
  persistence.requestLoad(() => { loaded = true })
  assert.equal(persistence.showUnsavedModal.value, true)
  assert.equal(loaded, false)

  // Confirm discard loads
  persistence.confirmDiscardAndLoad()
  assert.equal(persistence.showUnsavedModal.value, false)
  assert.equal(loaded, true)
})

