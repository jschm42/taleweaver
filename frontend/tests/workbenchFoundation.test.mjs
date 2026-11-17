import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'
import { nextTick } from 'vue'
import { checkText } from '../scripts/check_workbench_ui.mjs'

const tempFiles = []
after(() => tempFiles.forEach((file) => { try { unlinkSync(file) } catch { /* already gone */ } }))

async function load(path, name) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const tempFile = new URL(`./__temp_${name}.mjs`, import.meta.url)
  writeFileSync(tempFile, js)
  tempFiles.push(tempFile)
  return import(tempFile.href)
}

const dialogs = await load('../src/composables/useDialogs.ts', 'useDialogs')
const draftModule = await load('../src/composables/useDraft.ts', 'useDraft')

test('a confirm dialog resolves with the answer and leaves the queue', async () => {
  // Arrange
  const answer = dialogs.confirmDialog({ title: 'Delete?' })
  const [pending] = dialogs.dialogQueue.items

  // Act
  dialogs.settleDialog(pending.id, true)

  // Assert
  assert.equal(await answer, true)
  assert.equal(dialogs.dialogQueue.items.length, 0)
})

test('dialogs queue up and settle in any order', async () => {
  // Arrange
  const first = dialogs.confirmDialog({ title: 'First?' })
  const second = dialogs.promptDialog({ title: 'Name?' })
  const [a, b] = dialogs.dialogQueue.items

  // Act
  dialogs.settleDialog(b.id, 'Crypt theme')
  dialogs.settleDialog(a.id, false)

  // Assert
  assert.equal(await second, 'Crypt theme')
  assert.equal(await first, false)
})

test('a cancelled prompt resolves null and unknown ids are ignored', async () => {
  // Arrange
  const answer = dialogs.promptDialog({ title: 'Name?' })
  const [pending] = dialogs.dialogQueue.items

  // Act
  dialogs.settleDialog(9999, 'ignored')
  dialogs.settleDialog(pending.id, null)

  // Assert
  assert.equal(await answer, null)
})

test('changed keys compare top-level values deeply', () => {
  // Arrange
  const base = { title: 'A', tags: ['x'], nested: { a: 1 } }

  // Act
  const keys = draftModule.changedTopLevelKeys({ title: 'A', tags: ['x', 'y'], nested: { a: 2 } }, base)

  // Assert
  assert.deepEqual(keys.sort(), ['nested', 'tags'])
})

test('changed entries of a list are counted one by one', () => {
  // Arrange
  const base = [{ name: 'A' }, { name: 'B' }]

  // Act
  const keys = draftModule.changedTopLevelKeys([{ name: 'A' }, { name: 'B2' }, { name: 'C' }], base)

  // Assert
  assert.deepEqual(keys, ['1', '2'])
})

test('a draft tracks edits, resets and commits', async () => {
  // Arrange
  let source = { title: 'Old', count: 1 }
  const { draft, isDirty, changedCount, reset, commit } = draftModule.useDraft(() => source)

  // Act
  draft.value.title = 'New'
  const dirtyAfterEdit = isDirty.value
  reset()
  const titleAfterReset = draft.value.title
  draft.value.count = 2
  let saved = null
  const ok = await commit((value) => { saved = value })

  // Assert
  assert.equal(dirtyAfterEdit, true)
  assert.equal(titleAfterReset, 'Old')
  assert.equal(ok, true)
  assert.deepEqual(saved, { title: 'Old', count: 2 })
  assert.equal(isDirty.value, false)
  assert.equal(changedCount.value, 0)
  assert.notEqual(source, saved, 'the source object is never mutated')
})

test('a clean draft follows its source, a dirty one keeps the edits', async () => {
  // Arrange
  const { ref } = await import('vue')
  const source = ref({ title: 'A' })
  const { draft } = draftModule.useDraft(() => source.value)

  // Act
  source.value = { title: 'B' }
  await nextTick()
  const followed = draft.value.title
  draft.value.title = 'Mine'
  source.value = { title: 'C' }
  await nextTick()

  // Assert
  assert.equal(followed, 'B')
  assert.equal(draft.value.title, 'Mine')
})

test('a dirty draft becomes clean when the source arrives with the same values', async () => {
  // Arrange
  const { ref } = await import('vue')
  const source = ref({ title: 'A', mode: 'x' })
  const { draft, isDirty } = draftModule.useDraft(() => source.value)
  draft.value.title = 'B'

  // Act
  source.value = { title: 'B', mode: 'x' }
  await nextTick()

  // Assert
  assert.equal(isDirty.value, false)
  assert.equal(draft.value.title, 'B')
})

test('the UI check flags off-token styling', () => {
  // Arrange
  const line = '<p class="text-[10px] bg-slate-900 text-emerald-400 font-black tracking-widest rounded-2xl" style="color: #ff0000">'

  // Act
  const rules = checkText(line).map((finding) => finding.rule)

  // Assert
  assert.deepEqual(
    [...new Set(rules)].sort(),
    ['arbitrary-text', 'font-black', 'hex-color', 'palette-color', 'radius', 'tracking'],
  )
})

test('the UI check accepts tokens, slot names and ignore markers', () => {
  // Arrange
  const text = [
    '<div class="bg-wb-surface text-wb-muted rounded-xl wb-hint border-wb-line">',
    '<template #footer>',
    '<p class="text-slate-400"> <!-- workbench-ui-ignore -->',
  ].join('\n')

  // Act
  const findings = checkText(text)

  // Assert
  assert.deepEqual(findings, [])
})
