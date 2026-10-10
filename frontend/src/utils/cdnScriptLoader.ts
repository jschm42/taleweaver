/**
 * Utility to dynamically load CodeMirror 5 and Skulpt via CDN
 * for browser-based Python scripting with syntax highlighting and in-browser execution.
 */

const CODEMIRROR_CSS = [
  'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css',
]

const CODEMIRROR_SCRIPTS = [
  'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchbrackets.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closebrackets.min.js',
]

const SKULPT_SCRIPTS = [
  'https://cdn.jsdelivr.net/npm/skulpt@1.2.0/dist/skulpt.min.js',
  'https://cdn.jsdelivr.net/npm/skulpt@1.2.0/dist/skulpt-stdlib.js',
]

let loadPromise: Promise<{ codeMirrorLoaded: boolean; skulptLoaded: boolean }> | null = null

function loadStyle(href: string): Promise<void> {
  return new Promise((resolve) => {
    if (document.querySelector(`link[href="${href}"]`)) {
      resolve()
      return
    }
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = href
    link.onload = () => resolve()
    link.onerror = () => {
      console.warn(`[CDNLoader] Failed to load stylesheet: ${href}`)
      resolve()
    }
    document.head.appendChild(link)
  })
}

function loadScript(src: string): Promise<boolean> {
  return new Promise((resolve) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve(true)
      return
    }
    const script = document.createElement('script')
    script.src = src
    script.async = false
    script.onload = () => resolve(true)
    script.onerror = () => {
      console.warn(`[CDNLoader] Failed to load script: ${src}`)
      resolve(false)
    }
    document.head.appendChild(script)
  })
}

export function isCodeMirrorAvailable(): boolean {
  return typeof window !== 'undefined' && typeof (window as any).CodeMirror === 'function'
}

export function isSkulptAvailable(): boolean {
  return typeof window !== 'undefined' && !!(window as any).Sk
}

export async function loadCodeMirrorAndSkulpt(): Promise<{
  codeMirrorLoaded: boolean
  skulptLoaded: boolean
}> {
  if (isCodeMirrorAvailable() && isSkulptAvailable()) {
    return { codeMirrorLoaded: true, skulptLoaded: true }
  }

  if (loadPromise) {
    return loadPromise
  }

  loadPromise = (async () => {
    try {
      // 1. Load Stylesheets
      await Promise.all(CODEMIRROR_CSS.map(loadStyle))

      // 2. Load CodeMirror Scripts Sequentially
      for (const src of CODEMIRROR_SCRIPTS) {
        await loadScript(src)
      }

      // 3. Load Skulpt Scripts Sequentially
      for (const src of SKULPT_SCRIPTS) {
        await loadScript(src)
      }

      const cmLoaded = isCodeMirrorAvailable()
      const skLoaded = isSkulptAvailable()

      if (skLoaded) {
        configureSkulpt()
      }

      return {
        codeMirrorLoaded: cmLoaded,
        skulptLoaded: skLoaded,
      }
    } catch (err) {
      console.error('[CDNLoader] Error loading CodeMirror or Skulpt:', err)
      return {
        codeMirrorLoaded: isCodeMirrorAvailable(),
        skulptLoaded: isSkulptAvailable(),
      }
    }
  })()

  return loadPromise
}

/**
 * Configure Skulpt environment
 */
export function configureSkulpt(outputCallback?: (text: string) => void) {
  if (!isSkulptAvailable()) return
  const Sk = (window as any).Sk
  Sk.configure({
    output: outputCallback || (() => {}),
    read: (filename: string) => {
      if (Sk.builtinFiles === undefined || Sk.builtinFiles['files'][filename] === undefined) {
        throw new Error(`File not found: '${filename}'`)
      }
      return Sk.builtinFiles['files'][filename]
    },
    retainPath: true,
    execLimit: 4000,
    __future__: Sk.python3,
  })
}

export interface SyntaxCheckResult {
  valid: boolean
  error?: string
  line?: number
  column?: number
}

/**
 * Perform instant in-browser syntax validation using Skulpt AST parser
 */
export function validatePythonSyntaxWithSkulpt(code: string): SyntaxCheckResult {
  if (!code || !code.trim()) {
    return { valid: true }
  }

  if (!isSkulptAvailable()) {
    return { valid: false, error: 'Python engine (Skulpt) is still loading. Please wait a moment.' }
  }

  const Sk = (window as any).Sk
  try {
    if (!Sk.__future__ || !Sk.__future__.python3) {
      configureSkulpt()
    }
    Sk.parse('<stdin>', code)
    return { valid: true }
  } catch (err: any) {
    let line: number | undefined
    let column: number | undefined

    if (err.traceback && err.traceback.length > 0) {
      line = err.traceback[0].lineno
    } else if (err.args && err.args.v && Array.isArray(err.args.v) && err.args.v.length >= 3) {
      line = typeof err.args.v[1] === 'number' ? err.args.v[1] : undefined
      column = typeof err.args.v[2] === 'number' ? err.args.v[2] : undefined
    } else if (typeof err.lineno === 'number') {
      line = err.lineno
      column = err.colno
    }

    const msg = err.toString ? err.toString() : String(err)
    return {
      valid: false,
      error: msg,
      line,
      column,
    }
  }
}

export interface ScriptRunResult {
  success: boolean
  output: string
  error?: string
}

/**
 * Run Python script inside browser using Skulpt with TaleWeaver mock APIs (tw.*)
 */
export async function runPythonWithSkulpt(code: string): Promise<ScriptRunResult> {
  if (!code || !code.trim()) {
    return { success: true, output: '(Empty script, nothing to run)' }
  }

  if (!isSkulptAvailable()) {
    return { success: false, output: '', error: 'Skulpt Python engine is not loaded.' }
  }

  const Sk = (window as any).Sk
  let stdout = ''

  configureSkulpt((text: string) => {
    stdout += text
  })

  // TaleWeaver simulation environment
  const twMockHeader = `
class _MockPlayer:
    def __init__(self):
        self.stats = {"hp": 100, "strength": 10, "dexterity": 10, "mana": 50, "stamina": 100}
        self.inventory = []
    def get_stat(self, name, default=0): 
        return self.stats.get(name, default)
    def set_stat(self, name, val): 
        self.stats[name] = val
        print(f"[tw.player] set_stat: {name} = {val}")
    def damage(self, amount):
        self.stats["hp"] = max(0, self.stats.get("hp", 100) - amount)
        print(f"[tw.player] damage({amount}) -> HP: {self.stats['hp']}")
    def heal(self, amount):
        self.stats["hp"] = self.stats.get("hp", 100) + amount
        print(f"[tw.player] heal({amount}) -> HP: {self.stats['hp']}")
    def add_item(self, item_id): 
        self.inventory.append(item_id)
        print(f"[tw.player] add_item: '{item_id}'")
    def remove_item(self, item_id):
        if item_id in self.inventory: self.inventory.remove(item_id)
        print(f"[tw.player] remove_item: '{item_id}'")
    def has_item(self, item_id): 
        return item_id in self.inventory

class _MockScene:
    def __init__(self):
        self.id = "CURRENT_SCENE"
        self.attributes = {}
    def get_attribute(self, k, default=None): 
        return self.attributes.get(k, default)
    def set_attribute(self, k, v):
        self.attributes[k] = v
        print(f"[tw.scene] set_attribute: {k} = {v}")

class _MockNPC:
    def __init__(self, npc_id="NPC"):
        self.id = npc_id
        self.attributes = {}
    def get_attribute(self, k, default=None):
        return self.attributes.get(k, default)
    def set_attribute(self, k, v):
        self.attributes[k] = v
        print(f"[tw.npc.{self.id}] set_attribute: {k} = {v}")

class _MockStory:
    def show_message(self, text):
        print(f"[tw.story.show_message] {text}")
    def narrate(self, text):
        print(f"[tw.story.narrate] {text}")

class _MockTW:
    def __init__(self):
        self.player = _MockPlayer()
        self.scene = _MockScene()
        self.story = _MockStory()
        self.vars = {}
    def get_npc(self, npc_id): 
        return _MockNPC(npc_id)
    def narrate(self, text): 
        self.story.narrate(text)
    def say(self, speaker, text): 
        print(f"[{speaker}] {text}")
    def log(self, text): 
        print(f"[LOG] {text}")

tw = _MockTW()
`

  try {
    const fullCode = twMockHeader + '\n' + code
    await Sk.misceval.asyncToPromise(() => {
      return Sk.importMainWithBody('<stdin>', false, fullCode, true)
    })
    return {
      success: true,
      output: stdout.trim() || '(Execution finished with no output)',
    }
  } catch (err: any) {
    const msg = err.toString ? err.toString() : String(err)
    return {
      success: false,
      output: stdout.trim(),
      error: msg,
    }
  }
}
