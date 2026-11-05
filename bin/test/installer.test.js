// Tests for the skill installer (bin/install-skill.js and bin/lib/*).
// Run with: node --test bin/

import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, beforeEach, describe, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { FORMATS, parseArgs, UsageError } from '../lib/args.js';
import { parseFrontmatter } from '../lib/frontmatter.js';
import { buildPlan, executePlan, inspectTarget } from '../lib/plan.js';
import {
  BUILTIN_COMPANIONS,
  collectCompanions,
  discoverSkills,
  findSkill,
  resolveSkillsRoot,
  SKILLS_SUBDIR,
  toSafeRelative,
} from '../lib/skills.js';

const execFileAsync = promisify(execFile);
const BIN_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PACKAGE_ROOT = path.dirname(BIN_DIR);
const CLI = path.join(BIN_DIR, 'install-skill.js');
const CONCEPT_SKILL = 'taleweaver-adventure-concept-creator';

const tempDirs = [];

function makeTempDir(prefix = 'tw-skills-') {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  tempDirs.push(dir);
  return dir;
}

function writeFile(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
}

function listFiles(root) {
  return fs
    .readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => path.relative(root, path.join(entry.parentPath ?? entry.path, entry.name)))
    .map((rel) => rel.split(path.sep).join('/'))
    .sort();
}

/** Run the CLI; resolves with { code, stdout, stderr } instead of rejecting on non-zero exit. */
async function runCli(args, { cwd } = {}) {
  try {
    const { stdout, stderr } = await execFileAsync(process.execPath, [CLI, ...args], {
      cwd: cwd ?? makeTempDir('tw-cwd-'),
      env: { ...process.env, NO_COLOR: '1' },
    });
    return { code: 0, stdout, stderr };
  } catch (error) {
    if (typeof error.code !== 'number') {
      throw error;
    }
    return { code: error.code, stdout: error.stdout, stderr: error.stderr };
  }
}

after(() => {
  for (const dir of tempDirs) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// ---------------------------------------------------------------------------
// 1. Argument parsing
// ---------------------------------------------------------------------------

describe('parseArgs', () => {
  test('returns defaults for an empty argv', () => {
    assert.deepEqual(parseArgs([]), {
      skill: undefined,
      target: undefined,
      all: false,
      list: false,
      format: 'antigravity',
      dryRun: false,
      force: false,
      help: false,
      version: false,
    });
  });

  test('reads skill and target from positionals', () => {
    const options = parseArgs(['my-skill', './out']);
    assert.equal(options.skill, 'my-skill');
    assert.equal(options.target, './out');
  });

  test('treats the single positional as the target when --all is set', () => {
    const options = parseArgs(['--all', './out']);
    assert.equal(options.all, true);
    assert.equal(options.skill, undefined);
    assert.equal(options.target, './out');
  });

  test('explicit --skill leaves the positional for the target', () => {
    const options = parseArgs(['--skill', 'a', './out']);
    assert.equal(options.skill, 'a');
    assert.equal(options.target, './out');
  });

  test('explicit --target leaves the positional for the skill', () => {
    const options = parseArgs(['--target', './out', 'a']);
    assert.equal(options.skill, 'a');
    assert.equal(options.target, './out');
  });

  for (const [flag, key] of [
    ['-s', 'skill'],
    ['--skill', 'skill'],
    ['-t', 'target'],
    ['--target', 'target'],
    ['-d', 'target'],
    ['--dest', 'target'],
  ]) {
    test(`value flag ${flag} sets ${key}`, () => {
      assert.equal(parseArgs([flag, 'value'])[key], 'value');
    });
  }

  for (const flag of ['-f', '--format', '--agent']) {
    test(`format flag ${flag} sets format`, () => {
      assert.equal(parseArgs([flag, 'claude']).format, 'claude');
    });
  }

  for (const [flag, key] of [
    ['-a', 'all'],
    ['--all', 'all'],
    ['-l', 'list'],
    ['--list', 'list'],
    ['--dry-run', 'dryRun'],
    ['--force', 'force'],
    ['-h', 'help'],
    ['--help', 'help'],
    ['-v', 'version'],
    ['--version', 'version'],
  ]) {
    test(`boolean flag ${flag} sets ${key}`, () => {
      assert.equal(parseArgs([flag])[key], true);
    });
  }

  test('accepts inline --flag=value syntax', () => {
    const options = parseArgs(['--skill=a', '--target=./out', '--format=direct']);
    assert.equal(options.skill, 'a');
    assert.equal(options.target, './out');
    assert.equal(options.format, 'direct');
  });

  test('keeps "=" characters after the first one in inline values', () => {
    assert.equal(parseArgs(['--target=a=b']).target, 'a=b');
  });

  test('normalizes format case and whitespace', () => {
    assert.equal(parseArgs(['--format', '  CLAUDE ']).format, 'claude');
  });

  test('accepts every documented format', () => {
    for (const format of FORMATS) {
      assert.equal(parseArgs(['--format', format]).format, format);
    }
  });

  test('accepts "-" as a positional and as a flag value', () => {
    assert.equal(parseArgs(['-']).skill, '-');
    assert.equal(parseArgs(['--target', '-']).target, '-');
  });

  test('treats everything after "--" as positionals', () => {
    const options = parseArgs(['--', '--weird-skill', '-target']);
    assert.equal(options.skill, '--weird-skill');
    assert.equal(options.target, '-target');
  });

  test('the last occurrence of a repeated value flag wins', () => {
    assert.equal(parseArgs(['-t', 'one', '--dest', 'two']).target, 'two');
  });

  const errorCases = [
    [['--bogus'], /Unknown option: --bogus/],
    [['-x'], /Unknown option: -x/],
    [['--skill'], /--skill requires a value/],
    [['--target', '--force'], /--target requires a value/],
    [['--format', 'vim'], /Unknown format "vim"/],
    [['--format='], /Unknown format ""/],
    [['--force=yes'], /--force does not take a value/],
    [['--all', '--skill', 'a'], /either --skill <name> or --all/],
    [['a', 'b', 'c'], /Unexpected argument\(s\): c/],
    [['--all', 'a', 'b'], /Unexpected argument\(s\): b/],
    [['a', '   '], /Target directory must not be empty/],
    [['--target='], /Target directory must not be empty/],
  ];
  for (const [argv, message] of errorCases) {
    test(`rejects ${JSON.stringify(argv)} with a UsageError`, () => {
      assert.throws(
        () => parseArgs(argv),
        (error) => error instanceof UsageError && message.test(error.message),
      );
    });
  }
});

// ---------------------------------------------------------------------------
// 2. Frontmatter parsing
// ---------------------------------------------------------------------------

describe('parseFrontmatter', () => {
  test('returns empty data and the full body without frontmatter', () => {
    assert.deepEqual(parseFrontmatter('# Title\ntext'), { data: {}, body: '# Title\ntext' });
  });

  test('parses scalars and strips the frontmatter from the body', () => {
    const { data, body } = parseFrontmatter('---\nname: demo\nversion: 1.2\n---\n# Body\n');
    assert.deepEqual(data, { name: 'demo', version: '1.2' });
    assert.equal(body, '# Body\n');
  });

  test('unquotes single- and double-quoted strings', () => {
    const { data } = parseFrontmatter('---\na: "hello: world"\nb: \'single\'\nc: "\n---\n');
    assert.equal(data.a, 'hello: world');
    assert.equal(data.b, 'single');
    assert.equal(data.c, '"');
  });

  test('parses inline lists', () => {
    const { data } = parseFrontmatter('---\ndocs: [docs/a.md, "docs/b.md", , \'c\']\nempty: []\n---\n');
    assert.deepEqual(data.docs, ['docs/a.md', 'docs/b.md', 'c']);
    assert.deepEqual(data.empty, []);
  });

  test('parses block lists and stops at the next key', () => {
    const text = '---\ndocs:\n  - docs/a.md\n  - "docs/b.md"\n\n  - docs/c.md\nname: x\n---\n';
    const { data } = parseFrontmatter(text);
    assert.deepEqual(data.docs, ['docs/a.md', 'docs/b.md', 'docs/c.md']);
    assert.equal(data.name, 'x');
  });

  test('parses unindented block list items', () => {
    const { data } = parseFrontmatter('---\nfiles:\n- one\n- two\nname: n\n---\n');
    assert.deepEqual(data.files, ['one', 'two']);
    assert.equal(data.name, 'n');
  });

  test('a key with no value and no list items yields an empty list', () => {
    const { data } = parseFrontmatter('---\ndocs:\nname: n\n---\n');
    assert.deepEqual(data.docs, []);
  });

  test('joins folded block scalars with spaces', () => {
    const text = '---\ndescription: >\n  First line\n  second line.\nname: n\n---\n';
    const { data } = parseFrontmatter(text);
    assert.equal(data.description, 'First line second line.');
    assert.equal(data.name, 'n');
  });

  test('joins literal block scalars with newlines and accepts chomping indicators', () => {
    const { data } = parseFrontmatter('---\nnotes: |-\n  one\n  two\n---\n');
    assert.equal(data.notes, 'one\ntwo');
  });

  test('handles CRLF line endings and a UTF-8 BOM', () => {
    const { data, body } = parseFrontmatter('\uFEFF---\r\nname: crlf\r\n---\r\nBody\r\n');
    assert.deepEqual(data, { name: 'crlf' });
    assert.equal(body, 'Body\n');
  });

  test('accepts frontmatter at the very end of the file', () => {
    const { data, body } = parseFrontmatter('---\nname: end\n---');
    assert.deepEqual(data, { name: 'end' });
    assert.equal(body, '');
  });

  test('ignores comments, nested keys and malformed lines', () => {
    const text = '---\n# comment\nname: n\n  nested: ignored\nnot a key\n1bad: x\n---\n';
    assert.deepEqual(parseFrontmatter(text).data, { name: 'n' });
  });

  test('treats an unterminated frontmatter block as body', () => {
    const text = '---\nname: n\nno closing fence\n';
    assert.deepEqual(parseFrontmatter(text), { data: {}, body: text });
  });

  test('requires the opening fence on the first line', () => {
    const text = '\n---\nname: n\n---\n';
    assert.deepEqual(parseFrontmatter(text).data, {});
  });
});

// ---------------------------------------------------------------------------
// 3. Skill discovery and companion collection
// ---------------------------------------------------------------------------

/** Create a source root with .agents/skills and return helpers to populate it. */
function makeSourceRoot() {
  const root = makeTempDir('tw-src-');
  const skillsDir = path.join(root, SKILLS_SUBDIR);
  fs.mkdirSync(skillsDir, { recursive: true });
  const addSkill = (id, frontmatter = '', extraFiles = {}) => {
    const dir = path.join(skillsDir, id);
    const header = frontmatter ? `---\n${frontmatter}\n---\n` : '';
    writeFile(path.join(dir, 'SKILL.md'), `${header}# ${id}\n`);
    for (const [rel, content] of Object.entries(extraFiles)) {
      writeFile(path.join(dir, rel), content);
    }
    return dir;
  };
  return { root, skillsDir, addSkill };
}

function loadSkill(skillsDir, id) {
  return findSkill(discoverSkills(skillsDir), id);
}

describe('resolveSkillsRoot', () => {
  test('returns the first candidate containing .agents/skills', () => {
    const empty = makeTempDir();
    const { root, skillsDir } = makeSourceRoot();
    const other = makeSourceRoot();
    assert.deepEqual(resolveSkillsRoot([empty, root, other.root]), { sourceRoot: root, skillsDir });
  });

  test('ignores a .agents/skills path that is a file', () => {
    const root = makeTempDir();
    writeFile(path.join(root, SKILLS_SUBDIR), 'not a dir');
    assert.equal(resolveSkillsRoot([root]), null);
  });

  test('returns null when nothing matches', () => {
    assert.equal(resolveSkillsRoot([makeTempDir(), path.join(os.tmpdir(), 'tw-missing-xyz')]), null);
  });
});

describe('discoverSkills and findSkill', () => {
  test('lists directories with SKILL.md sorted by id', () => {
    const { skillsDir, addSkill } = makeSourceRoot();
    addSkill('zeta', 'name: zeta\ndescription: Last');
    addSkill('alpha', 'name: Alpha Skill\ndescription: >\n  First\n  skill.');
    addSkill('no-frontmatter');
    fs.mkdirSync(path.join(skillsDir, 'no-skill-file'));
    addSkill('.hidden', 'name: hidden');
    writeFile(path.join(skillsDir, 'README.md'), 'not a skill');

    const skills = discoverSkills(skillsDir);
    assert.deepEqual(
      skills.map((s) => s.id),
      ['alpha', 'no-frontmatter', 'zeta'],
    );
    const alpha = skills[0];
    assert.equal(alpha.name, 'Alpha Skill');
    assert.equal(alpha.description, 'First skill.');
    assert.equal(alpha.dir, path.join(skillsDir, 'alpha'));
    assert.equal(alpha.frontmatter.name, 'Alpha Skill');
    assert.equal(skills[1].name, 'no-frontmatter');
    assert.equal(skills[1].description, '');
  });

  test('falls back to the directory name for non-string or empty names', () => {
    const { skillsDir, addSkill } = makeSourceRoot();
    addSkill('listy', 'name: [a, b]\ndescription: [x]');
    addSkill('blank', 'name: ""');
    const [blank, listy] = discoverSkills(skillsDir);
    assert.equal(blank.name, 'blank');
    assert.equal(listy.name, 'listy');
    assert.equal(listy.description, '');
  });

  test('findSkill matches id or name, case-insensitively and trimmed', () => {
    const { skillsDir, addSkill } = makeSourceRoot();
    addSkill('my-skill', 'name: Fancy Name');
    const skills = discoverSkills(skillsDir);
    assert.equal(findSkill(skills, 'MY-SKILL ')?.id, 'my-skill');
    assert.equal(findSkill(skills, 'fancy name')?.id, 'my-skill');
    assert.equal(findSkill(skills, 'other'), undefined);
  });

  test('discovers the skills shipped with this repository', () => {
    const located = resolveSkillsRoot([PACKAGE_ROOT]);
    assert.ok(located);
    const ids = discoverSkills(located.skillsDir).map((s) => s.id);
    assert.ok(ids.includes(CONCEPT_SKILL));
  });
});

describe('toSafeRelative', () => {
  const cases = [
    ['docs/a.md', 'docs/a.md'],
    ['./docs/a.md', 'docs/a.md'],
    ['  docs/a.md  ', 'docs/a.md'],
    ['docs\\win\\a.md', 'docs/win/a.md'],
    ['docs/x/../a.md', 'docs/a.md'],
    ['docs/a.md#section', 'docs/a.md'],
    ['/etc/passwd', null],
    ['C:/Windows/a.md', null],
    ['c:\\temp\\a.md', null],
    ['../secret.md', null],
    ['docs/../../secret.md', null],
    ['..', null],
    ['.', null],
    ['', null],
    ['   ', null],
    ['https://example.com/a.md', null],
    ['file:///etc/passwd', null],
    [42, null],
    [undefined, null],
  ];
  for (const [input, expected] of cases) {
    test(`${JSON.stringify(input)} -> ${JSON.stringify(expected)}`, () => {
      assert.equal(toSafeRelative(input), expected);
    });
  }
});

describe('collectCompanions', () => {
  test('collects companions from frontmatter keys relative to the source root', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    writeFile(path.join(root, 'docs/a.md'), 'A');
    writeFile(path.join(root, 'docs/b.md'), 'B');
    writeFile(path.join(root, 'notes/c.md'), 'C');
    addSkill('s', 'docs: [docs/a.md]\nfiles:\n  - docs/b.md\nreferences: [notes/c.md]');

    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(
      result.files.map((f) => [f.relPath, f.source, f.aliases]),
      [
        ['docs/a.md', path.join(root, 'docs/a.md'), []],
        ['docs/b.md', path.join(root, 'docs/b.md'), []],
        ['notes/c.md', path.join(root, 'notes/c.md'), []],
      ],
    );
    assert.deepEqual(result.missing, []);
    assert.deepEqual(result.warnings, []);
  });

  test('reads manifest files including object entries and the taleweaver namespace', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    for (const name of ['m1', 'm2', 'm3', 'm4', 'm5']) {
      writeFile(path.join(root, `docs/${name}.md`), name);
    }
    addSkill('s', '', {
      'manifest.json': JSON.stringify({ docs: ['docs/m1.md', { path: 'docs/m2.md' }] }),
      'skill.json': JSON.stringify({ companion_files: [{ src: 'docs/m3.md' }, 7, null] }),
      'package.json': JSON.stringify({
        taleweaver: { companionFiles: [{ source: 'docs/m4.md' }] },
        files: ['docs/m5.md'],
      }),
    });

    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(result.files.map((f) => f.relPath).sort(), [
      'docs/m1.md',
      'docs/m2.md',
      'docs/m3.md',
      'docs/m4.md',
      'docs/m5.md',
    ]);
  });

  test('warns about unreadable manifests and keeps going', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    writeFile(path.join(root, 'docs/a.md'), 'A');
    addSkill('s', 'docs: [docs/a.md]', { 'manifest.json': '{ not json' });

    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(
      result.files.map((f) => f.relPath),
      ['docs/a.md'],
    );
    assert.equal(result.warnings.length, 1);
    assert.match(result.warnings[0], /Ignoring unreadable manifest\.json/);
  });

  test('skips unsafe paths with a warning and URLs silently', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    addSkill('s', 'docs: [../outside.md, /etc/passwd, "https://example.com/x.md"]');

    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(result.files, []);
    assert.deepEqual(result.missing, []);
    assert.equal(result.warnings.length, 2);
    assert.match(result.warnings[0], /unsafe companion path "\.\.\/outside\.md" in s/);
    assert.match(result.warnings[1], /unsafe companion path "\/etc\/passwd"/);
  });

  test('reports missing companions once each', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    addSkill('s', 'docs: [docs/nope.md, ./docs/nope.md]');
    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(result.missing, ['docs/nope.md']);
  });

  test('de-duplicates companions listed in several places', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    writeFile(path.join(root, 'docs/a.md'), 'A');
    addSkill('s', 'docs: [docs/a.md, ./docs/a.md]\nfiles: [docs/x/../a.md]', {
      'manifest.json': JSON.stringify({ docs: ['docs/a.md'] }),
    });
    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.equal(result.files.length, 1);
  });

  test('skips companions that already live inside the skill directory', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    addSkill('s', 'docs: [references/guide.md]', { 'references/guide.md': 'inside' });
    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(result.files, []);
    assert.deepEqual(result.missing, []);
  });

  test('prefers the source root copy over a skill-local copy', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    writeFile(path.join(root, 'shared/guide.md'), 'root copy');
    addSkill('s', 'docs: [shared/guide.md]', { 'shared/guide.md': 'local copy' });
    const [file] = collectCompanions(loadSkill(skillsDir, 's'), root).files;
    assert.equal(file.source, path.join(root, 'shared/guide.md'));
  });

  test('ignores directories named as companions', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    fs.mkdirSync(path.join(root, 'docs/folder'), { recursive: true });
    addSkill('s', 'docs: [docs/folder]');
    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(result.files, []);
    assert.deepEqual(result.missing, ['docs/folder']);
  });

  test('maps aliased (misspelled) references to the canonical file', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    writeFile(path.join(root, 'docs/scripting_engine.md'), 'engine');
    addSkill('s', 'docs: [docs/scripting-enginge.md]');
    const result = collectCompanions(loadSkill(skillsDir, 's'), root);
    assert.deepEqual(result.files, [
      {
        source: path.join(root, 'docs/scripting_engine.md'),
        relPath: 'docs/scripting_engine.md',
        aliases: ['docs/scripting-enginge.md'],
      },
    ]);
  });

  test('includes built-in companions for the concept creator skill', () => {
    const { root, skillsDir, addSkill } = makeSourceRoot();
    const builtins = BUILTIN_COMPANIONS[CONCEPT_SKILL];
    builtins.forEach((rel) => writeFile(path.join(root, rel), rel));
    addSkill(CONCEPT_SKILL);
    const result = collectCompanions(loadSkill(skillsDir, CONCEPT_SKILL), root);
    assert.deepEqual(
      result.files.map((f) => f.relPath),
      builtins,
    );
  });

  test('resolves all built-in companions against the real repository', () => {
    const located = resolveSkillsRoot([PACKAGE_ROOT]);
    const skill = loadSkill(located.skillsDir, CONCEPT_SKILL);
    const result = collectCompanions(skill, located.sourceRoot);
    assert.deepEqual(result.missing, []);
    assert.deepEqual(
      result.files.map((f) => f.relPath),
      BUILTIN_COMPANIONS[CONCEPT_SKILL],
    );
  });
});

// ---------------------------------------------------------------------------
// 4. Plan building and execution
// ---------------------------------------------------------------------------

describe('inspectTarget', () => {
  test('reports a missing target as fresh', () => {
    const target = path.join(makeTempDir(), 'missing');
    assert.deepEqual(inspectTarget(target), { exists: false, fresh: true, project: false });
  });

  test('reports an empty directory as fresh', () => {
    assert.deepEqual(inspectTarget(makeTempDir()), { exists: true, fresh: true, project: false });
  });

  test('reports a non-empty directory without markers as existing', () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'notes.txt'), 'x');
    assert.deepEqual(inspectTarget(target), { exists: true, fresh: false, project: false });
  });

  for (const marker of ['.git', '.agents', '.claude', 'package.json', 'pyproject.toml']) {
    test(`detects a project by its ${marker} marker`, () => {
      const target = makeTempDir();
      writeFile(path.join(target, marker), '');
      assert.equal(inspectTarget(target).project, true);
    });
  }

  test('throws when the target is a file', () => {
    const file = path.join(makeTempDir(), 'file.txt');
    writeFile(file, 'x');
    assert.throws(() => inspectTarget(file), /not a directory/);
  });
});

describe('buildPlan and executePlan', () => {
  let source;
  let skill;
  let companions;

  beforeEach(() => {
    source = makeSourceRoot();
    writeFile(path.join(source.root, 'docs/guide.md'), 'guide');
    writeFile(path.join(source.root, 'docs/scripting_engine.md'), 'engine');
    source.addSkill('demo', 'name: demo\ndocs: [docs/guide.md, docs/scripting_engine.md]', {
      'references/extra.md': 'extra',
      'node_modules/dep/index.js': 'ignored',
      '.DS_Store': 'ignored',
    });
    skill = loadSkill(source.skillsDir, 'demo');
    companions = collectCompanions(skill, source.root);
  });

  function context(target, overrides = {}) {
    return {
      ...inspectTarget(target),
      target,
      format: 'antigravity',
      multi: false,
      force: false,
      warnings: [],
      ...overrides,
    };
  }

  function destinations(plan, target) {
    return plan.map((op) => path.relative(target, op.dest).split(path.sep).join('/')).sort();
  }

  test('fresh target, antigravity: bundle, root companions and flat SKILL.md', () => {
    const target = path.join(makeTempDir(), 'new-project');
    const plan = buildPlan(context(target), [{ skill, companions }]);

    assert.deepEqual(destinations(plan, target), [
      '.agents/skills/demo/SKILL.md',
      '.agents/skills/demo/docs/guide.md',
      '.agents/skills/demo/docs/scripting-enginge.md',
      '.agents/skills/demo/docs/scripting_engine.md',
      '.agents/skills/demo/references/extra.md',
      'SKILL.md',
      'docs/guide.md',
      'docs/scripting-enginge.md',
      'docs/scripting_engine.md',
    ]);
    assert.ok(plan.every((op) => op.status === 'create' && !op.blocked && op.skill === 'demo'));
  });

  test('fresh target, claude: claude bundle plus the project layout', () => {
    const target = makeTempDir();
    const plan = buildPlan(context(target, { format: 'claude' }), [{ skill, companions }]);
    const dests = destinations(plan, target);
    assert.ok(dests.includes('.claude/skills/demo/SKILL.md'));
    assert.ok(dests.includes('.claude/skills/demo/docs/guide.md'));
    assert.ok(dests.includes('.agents/skills/demo/SKILL.md'));
    assert.ok(dests.includes('docs/guide.md'));
    assert.ok(dests.includes('SKILL.md'));
    assert.equal(dests.length, 14);
  });

  test('existing non-project directory: only the primary bundle', () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'notes.txt'), 'x');
    const plan = buildPlan(context(target), [{ skill, companions }]);
    assert.deepEqual(destinations(plan, target), [
      '.agents/skills/demo/SKILL.md',
      '.agents/skills/demo/docs/guide.md',
      '.agents/skills/demo/docs/scripting-enginge.md',
      '.agents/skills/demo/docs/scripting_engine.md',
      '.agents/skills/demo/references/extra.md',
    ]);
  });

  test('existing project: bundle plus companions at the project root', () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'package.json'), '{}');
    const plan = buildPlan(context(target, { format: 'claude' }), [{ skill, companions }]);
    const dests = destinations(plan, target);
    assert.ok(dests.includes('.claude/skills/demo/SKILL.md'));
    assert.ok(dests.includes('docs/guide.md'));
    assert.ok(!dests.includes('SKILL.md'));
    assert.ok(!dests.some((d) => d.startsWith('.agents/')));
  });

  test('direct format, single skill in an existing directory writes into the target', () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'notes.txt'), 'x');
    const plan = buildPlan(context(target, { format: 'direct' }), [{ skill, companions }]);
    assert.deepEqual(destinations(plan, target), [
      'SKILL.md',
      'docs/guide.md',
      'docs/scripting-enginge.md',
      'docs/scripting_engine.md',
      'references/extra.md',
    ]);
  });

  test('direct format with several skills uses one folder per skill and no flat SKILL.md', () => {
    source.addSkill('second', 'name: second');
    const second = loadSkill(source.skillsDir, 'second');
    const target = makeTempDir();
    const ctx = context(target, { format: 'direct', multi: true });
    const plan = buildPlan(ctx, [
      { skill, companions },
      { skill: second, companions: collectCompanions(second, source.root) },
    ]);
    const dests = destinations(plan, target);
    assert.ok(dests.includes('demo/SKILL.md'));
    assert.ok(dests.includes('second/SKILL.md'));
    assert.ok(dests.includes('.agents/skills/second/SKILL.md'));
    assert.ok(!dests.includes('SKILL.md'));
  });

  test('de-duplicates shared companions across skills (first skill wins)', () => {
    source.addSkill('second', 'docs: [docs/guide.md]');
    const second = loadSkill(source.skillsDir, 'second');
    const target = makeTempDir();
    const plan = buildPlan(context(target, { multi: true }), [
      { skill, companions },
      { skill: second, companions: collectCompanions(second, source.root) },
    ]);
    const rootGuide = plan.filter((op) => op.dest === path.join(target, 'docs', 'guide.md'));
    assert.equal(rootGuide.length, 1);
    assert.equal(rootGuide[0].skill, 'demo');
    assert.equal(new Set(plan.map((op) => op.dest)).size, plan.length);
  });

  test('skips symbolic links inside the skill with a warning', (t) => {
    const link = path.join(skill.dir, 'link.md');
    try {
      fs.symlinkSync(path.join(source.root, 'docs/guide.md'), link);
    } catch {
      t.skip('symlinks not supported on this platform');
      return;
    }
    const target = makeTempDir();
    const ctx = context(target);
    const plan = buildPlan(ctx, [{ skill, companions }]);
    assert.ok(!plan.some((op) => op.dest.endsWith('link.md')));
    assert.ok(ctx.warnings.some((w) => /Skipping symbolic link/.test(w)));
  });

  test('refuses destinations outside the target directory', () => {
    const target = makeTempDir();
    const evil = { files: [{ source: path.join(source.root, 'docs/guide.md'), relPath: '../escape.md', aliases: [] }] };
    assert.throws(
      () => buildPlan(context(target, { fresh: false, project: true }), [{ skill, companions: evil }]),
      /Refusing to write outside the target directory/,
    );
  });

  test('executePlan copies files and a rebuilt plan is fully unchanged', () => {
    const target = path.join(makeTempDir(), 'out');
    const plan = buildPlan(context(target), [{ skill, companions }]);
    assert.equal(executePlan(plan), plan.length);

    assert.equal(fs.readFileSync(path.join(target, 'docs/guide.md'), 'utf8'), 'guide');
    assert.equal(fs.readFileSync(path.join(target, 'docs/scripting-enginge.md'), 'utf8'), 'engine');
    assert.equal(
      fs.readFileSync(path.join(target, '.agents/skills/demo/references/extra.md'), 'utf8'),
      'extra',
    );
    assert.ok(!fs.existsSync(path.join(target, '.agents/skills/demo/node_modules')));
    assert.ok(!fs.existsSync(path.join(target, '.agents/skills/demo/.DS_Store')));

    const again = buildPlan(context(target), [{ skill, companions }]);
    assert.ok(again.length > 0);
    assert.ok(again.every((op) => op.status === 'unchanged' && !op.blocked));
    assert.equal(executePlan(again), 0);
  });

  test('changed files are blocked without --force and overwritten with it', () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'notes.txt'), 'x');
    const dest = path.join(target, '.agents/skills/demo/SKILL.md');
    writeFile(dest, 'locally modified');

    const blockedPlan = buildPlan(context(target), [{ skill, companions }]);
    const op = blockedPlan.find((o) => o.dest === dest);
    assert.equal(op.status, 'overwrite');
    assert.equal(op.blocked, true);
    executePlan(blockedPlan);
    assert.equal(fs.readFileSync(dest, 'utf8'), 'locally modified');

    const forcedPlan = buildPlan(context(target, { force: true }), [{ skill, companions }]);
    const forced = forcedPlan.find((o) => o.dest === dest);
    assert.equal(forced.status, 'overwrite');
    assert.equal(forced.blocked, false);
    executePlan(forcedPlan);
    assert.equal(fs.readFileSync(dest, 'utf8'), fs.readFileSync(path.join(skill.dir, 'SKILL.md'), 'utf8'));
  });

  test('a directory in place of a file is a conflict even with --force', () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'notes.txt'), 'x');
    const dest = path.join(target, '.agents/skills/demo/SKILL.md');
    fs.mkdirSync(dest, { recursive: true });

    const plan = buildPlan(context(target, { force: true }), [{ skill, companions }]);
    const op = plan.find((o) => o.dest === dest);
    assert.equal(op.status, 'conflict');
    assert.equal(op.blocked, true);
    executePlan(plan);
    assert.ok(fs.statSync(dest).isDirectory());
  });
});

// ---------------------------------------------------------------------------
// 5. End-to-end CLI
// ---------------------------------------------------------------------------

describe('install-skill.js CLI', () => {
  let skillIds;
  let version;

  before(() => {
    skillIds = discoverSkills(path.join(PACKAGE_ROOT, SKILLS_SUBDIR)).map((s) => s.id);
    version = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8')).version;
  });

  test('--help prints usage and exits 0', async () => {
    const { code, stdout } = await runCli(['--help']);
    assert.equal(code, 0);
    assert.match(stdout, /^Usage:/);
    assert.match(stdout, /--format <type>/);
    assert.match(stdout, /antigravity, claude, direct/);
  });

  test('--version prints the package version', async () => {
    for (const flag of ['--version', '-v']) {
      const { code, stdout } = await runCli([flag]);
      assert.equal(code, 0);
      assert.equal(stdout.trim(), `taleweaver-skills ${version}`);
    }
  });

  test('--list prints every packaged skill', async () => {
    const { code, stdout } = await runCli(['--list']);
    assert.equal(code, 0);
    assert.match(stdout, new RegExp(`Available skills \\(${skillIds.length}\\)`));
    for (const id of skillIds) {
      assert.match(stdout, new RegExp(`^  ${id}`, 'm'));
    }
  });

  test('unknown options exit with code 2 and a usage hint', async () => {
    const { code, stderr } = await runCli(['--bogus']);
    assert.equal(code, 2);
    assert.match(stderr, /error: Unknown option: --bogus/);
    assert.match(stderr, /--help" for usage/);
  });

  test('unknown skills exit with code 2 and list the available ones', async () => {
    const { code, stderr } = await runCli(['no-such-skill', makeTempDir()]);
    assert.equal(code, 2);
    assert.match(stderr, /Unknown skill "no-such-skill"/);
    assert.match(stderr, new RegExp(CONCEPT_SKILL));
  });

  test('a missing skill without a TTY exits with code 2', async () => {
    const { code, stderr } = await runCli(['--target', makeTempDir()]);
    assert.equal(code, 2);
    assert.match(stderr, /No skill given/);
  });

  test('a target that is a file exits with code 1', async () => {
    const file = path.join(makeTempDir(), 'file.txt');
    writeFile(file, 'x');
    const { code, stderr } = await runCli([CONCEPT_SKILL, file]);
    assert.equal(code, 1);
    assert.match(stderr, /not a directory/);
  });

  test('--dry-run reports the plan without writing anything', async () => {
    const target = path.join(makeTempDir(), 'dry');
    const { code, stdout } = await runCli([CONCEPT_SKILL, target, '--dry-run']);
    assert.equal(code, 0);
    assert.match(stdout, /\(fresh directory\)/);
    assert.match(stdout, /\[dry-run\] create {4}SKILL\.md/);
    assert.match(stdout, /Dry run complete: \d+ new, 0 overwritten, 0 unchanged\. No files were written\./);
    assert.equal(fs.existsSync(target), false);
  });

  test('installs into a fresh target and is idempotent on a second run', async () => {
    const target = path.join(makeTempDir(), 'fresh');
    const first = await runCli([CONCEPT_SKILL, target]);
    assert.equal(first.code, 0, first.stderr);
    assert.match(first.stdout, /\(fresh directory\)/);
    assert.match(first.stdout, /Done: (\d+) file\(s\) written \(\1 new, 0 overwritten, 0 unchanged\)/);

    const files = listFiles(target);
    const bundle = `.agents/skills/${CONCEPT_SKILL}`;
    for (const expected of [
      'SKILL.md',
      `${bundle}/SKILL.md`,
      ...BUILTIN_COMPANIONS[CONCEPT_SKILL],
      ...BUILTIN_COMPANIONS[CONCEPT_SKILL].map((rel) => `${bundle}/${rel}`),
      'docs/scripting-enginge.md',
      `${bundle}/docs/scripting-enginge.md`,
    ]) {
      assert.ok(files.includes(expected), `missing ${expected}`);
    }
    assert.ok(!files.some((f) => f.startsWith('.claude/')));
    assert.deepEqual(
      fs.readFileSync(path.join(target, 'docs/world-builder-syntax.md')),
      fs.readFileSync(path.join(PACKAGE_ROOT, 'docs/world-builder-syntax.md')),
    );

    const second = await runCli([CONCEPT_SKILL, target]);
    assert.equal(second.code, 0, second.stderr);
    assert.match(second.stdout, /\(project\)/);
    assert.match(second.stdout, /Done: 0 file\(s\) written \(0 new, 0 overwritten, \d+ unchanged\)/);
    assert.doesNotMatch(second.stdout, /^create/m);
    assert.deepEqual(listFiles(target), files);
  });

  test('--format claude installs into .claude/skills', async () => {
    const target = path.join(makeTempDir(), 'claude');
    const { code, stdout, stderr } = await runCli(['--skill', CONCEPT_SKILL, '--target', target, '--format', 'claude']);
    assert.equal(code, 0, stderr);
    assert.match(stdout, /format: claude/);

    const files = listFiles(target);
    assert.ok(files.includes(`.claude/skills/${CONCEPT_SKILL}/SKILL.md`));
    assert.ok(files.includes(`.claude/skills/${CONCEPT_SKILL}/docs/world-builder-syntax.md`));
    assert.ok(files.includes(`.agents/skills/${CONCEPT_SKILL}/SKILL.md`));
    assert.ok(files.includes('SKILL.md'));
  });

  test('locally modified files block the install until --force', async () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'notes.txt'), 'x');
    assert.equal((await runCli([CONCEPT_SKILL, target])).code, 0);

    const modified = path.join(target, `.agents/skills/${CONCEPT_SKILL}/SKILL.md`);
    writeFile(modified, 'local edit');

    const blocked = await runCli([CONCEPT_SKILL, target]);
    assert.equal(blocked.code, 1);
    assert.match(blocked.stderr, /1 file\(s\) already exist with different content/);
    assert.match(blocked.stderr, /Re-run with --force/);
    assert.equal(fs.readFileSync(modified, 'utf8'), 'local edit');

    const forced = await runCli([CONCEPT_SKILL, target, '--force']);
    assert.equal(forced.code, 0, forced.stderr);
    assert.match(forced.stdout, /1 overwritten/);
    assert.notEqual(fs.readFileSync(modified, 'utf8'), 'local edit');
  });

  test('--all --format direct installs every skill into its own folder', async () => {
    const target = makeTempDir();
    writeFile(path.join(target, 'notes.txt'), 'x');
    const { code, stderr } = await runCli(['--all', target, '--format', 'direct']);
    assert.equal(code, 0, stderr);
    const files = listFiles(target);
    for (const id of skillIds) {
      assert.ok(files.includes(`${id}/SKILL.md`), `missing ${id}/SKILL.md`);
    }
    assert.ok(!files.includes('SKILL.md'));
  });
});
