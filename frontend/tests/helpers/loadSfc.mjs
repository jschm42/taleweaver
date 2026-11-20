/**
 * Loads a Vue single-file component for node:test, including the components and TypeScript
 * modules it imports (`@/…` alias and relative paths). Each file is compiled once into
 * tests/.sfc-cache/ and imported from there; bare packages resolve from node_modules.
 *
 * Usage: const Component = await loadSfc('../src/components/admin/ComfyUISettings.vue', import.meta.url)
 */
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { compileScript, parse } from '@vue/compiler-sfc'
import ts from 'typescript'

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const SRC = resolve(FRONTEND, 'src')
const CACHE = resolve(FRONTEND, 'tests', '.sfc-cache')
const compiled = new Map()

rmSync(CACHE, { recursive: true, force: true })
mkdirSync(CACHE, { recursive: true })

function transpile(code) {
  return ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, verbatimModuleSyntax: false },
  }).outputText
}

function compileFile(file) {
  if (file.endsWith('.vue')) {
    const { descriptor } = parse(readFileSync(file, 'utf8'), { filename: file })
    const id = `sfc-${compiled.size}`
    return transpile(compileScript(descriptor, { id, inlineTemplate: true }).content)
  }
  return transpile(readFileSync(file, 'utf8'))
}

function resolveSource(specifier, fromFile) {
  if (specifier.startsWith('@/')) return withExtension(resolve(SRC, specifier.slice(2)))
  if (specifier.startsWith('.')) return withExtension(resolve(dirname(fromFile), specifier))
  return null
}

function withExtension(path) {
  return /\.(vue|ts|js|mjs)$/.test(path) ? path : `${path}.ts`
}

/** Compiles `file` and its local imports; returns the file URL of the compiled module. */
function build(file) {
  if (compiled.has(file)) return compiled.get(file)
  const target = resolve(CACHE, `m${compiled.size}.mjs`)
  const url = pathToFileURL(target).href
  compiled.set(file, url)
  const code = compileFile(file).replace(/(from\s+|import\s*\(\s*|import\s+)(['"])([^'"]+)\2/g, (match, prefix, quote, spec) => {
    if (spec.endsWith('.css')) return `${prefix}${quote}data:text/javascript,${quote}`
    const local = resolveSource(spec, file)
    const resolved = local ? build(local) : import.meta.resolve(spec, pathToFileURL(resolve(FRONTEND, 'package.json')).href)
    return `${prefix}${quote}${resolved}${quote}`
  })
  writeFileSync(target, code)
  return url
}

export async function loadSfc(relativePath, base) {
  const file = fileURLToPath(new URL(relativePath, base))
  return (await import(build(file))).default
}
