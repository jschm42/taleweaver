// Skill discovery and companion-file resolution.

import fs from 'node:fs';
import path from 'node:path';

import { parseFrontmatter } from './frontmatter.js';

export const SKILL_FILE = 'SKILL.md';
// Where this repo keeps its skills (the installer's source).
export const SOURCE_SKILLS_SUBDIR = path.join('.claude', 'skills');
// Install layout for the antigravity format.
export const SKILLS_SUBDIR = path.join('.agents', 'skills');

const MANIFEST_FILES = ['manifest.json', 'skill.json', 'package.json'];
const COMPANION_KEYS = [
  'docs',
  'documentation',
  'files',
  'companion_files',
  'companionFiles',
  'references',
];
const IGNORED_COMPANIONS = new Set([SKILL_FILE, ...MANIFEST_FILES]);
const URL_RE = /^[a-z][a-z0-9+.-]*:\/\//i;

// Companion docs a skill depends on even when its own metadata does not list them.
export const BUILTIN_COMPANIONS = {
  'taleweaver-adventure-concept-creator': [
    'docs/world-builder-blueprint-manual.md',
    'docs/world-builder-syntax.md',
    'docs/scripting_engine.md',
    'docs/specs/adventure_format.md',
  ],
};

// Extra install paths for a companion, kept for references that use a misspelled name.
export const COMPANION_ALIASES = {
  'docs/scripting_engine.md': ['docs/scripting-enginge.md'],
};

/**
 * Locate the .claude/skills source directory: next to the package first, then in the cwd.
 * Returns { sourceRoot, skillsDir } or null.
 */
export function resolveSkillsRoot(candidates) {
  for (const root of candidates) {
    const skillsDir = path.join(root, SOURCE_SKILLS_SUBDIR);
    if (fs.existsSync(skillsDir) && fs.statSync(skillsDir).isDirectory()) {
      return { sourceRoot: root, skillsDir };
    }
  }
  return null;
}

function readSkill(skillsDir, entry) {
  const dir = path.join(skillsDir, entry.name);
  const skillFile = path.join(dir, SKILL_FILE);
  if (!fs.existsSync(skillFile)) {
    return null;
  }
  const { data } = parseFrontmatter(fs.readFileSync(skillFile, 'utf8'));
  const name = typeof data.name === 'string' && data.name !== '' ? data.name : entry.name;
  const description = typeof data.description === 'string' ? data.description : '';
  return { id: entry.name, name, description, dir, frontmatter: data };
}

/** Return every skill directory that contains a SKILL.md, sorted by id. */
export function discoverSkills(skillsDir) {
  return fs
    .readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.'))
    .map((entry) => readSkill(skillsDir, entry))
    .filter(Boolean)
    .sort((a, b) => a.id.localeCompare(b.id));
}

export function findSkill(skills, query) {
  const needle = query.trim().toLowerCase();
  return skills.find((s) => s.id.toLowerCase() === needle || s.name.toLowerCase() === needle);
}

/**
 * Normalize a companion path to a safe, relative POSIX path.
 * Returns null for absolute paths, URLs and anything escaping its root (CWE-22).
 */
export function toSafeRelative(raw) {
  if (typeof raw !== 'string' || raw.trim() === '' || URL_RE.test(raw)) {
    return null;
  }
  const posix = raw.trim().replace(/\\/g, '/').replace(/#.*$/, '');
  if (posix.startsWith('/') || /^[a-zA-Z]:/.test(posix)) {
    return null;
  }
  const normalized = path.posix.normalize(posix).replace(/^\.\//, '');
  if (normalized === '.' || normalized === '..' || normalized.startsWith('../')) {
    return null;
  }
  return normalized;
}

function entryToPath(entry) {
  if (typeof entry === 'string') {
    return entry;
  }
  if (entry && typeof entry === 'object') {
    return entry.path ?? entry.src ?? entry.source ?? null;
  }
  return null;
}

function listFromKeys(container) {
  if (!container || typeof container !== 'object') {
    return [];
  }
  return COMPANION_KEYS.flatMap((key) => {
    const value = container[key];
    return Array.isArray(value) ? value.map(entryToPath) : [];
  });
}

function readManifestEntries(skillDir, warnings) {
  const entries = [];
  for (const fileName of MANIFEST_FILES) {
    const file = path.join(skillDir, fileName);
    if (!fs.existsSync(file)) {
      continue;
    }
    try {
      const json = JSON.parse(fs.readFileSync(file, 'utf8'));
      entries.push(...listFromKeys(json), ...listFromKeys(json.taleweaver));
    } catch (error) {
      warnings.push(`Ignoring unreadable ${fileName} in ${skillDir}: ${error.message}`);
    }
  }
  return entries;
}

function canonicalFor(relPath) {
  const match = Object.entries(COMPANION_ALIASES).find(([, aliases]) => aliases.includes(relPath));
  return match ? match[0] : relPath;
}

function isInside(parent, child) {
  const rel = path.relative(parent, child);
  return rel !== '' && !rel.startsWith('..') && !path.isAbsolute(rel);
}

function locateCompanion(relPath, skill, sourceRoot) {
  const canonical = canonicalFor(relPath);
  const candidates = [path.join(sourceRoot, canonical), path.join(skill.dir, canonical)];
  const source = candidates.find((file) => fs.existsSync(file) && fs.statSync(file).isFile());
  return source ? { source, relPath: canonical } : null;
}

/**
 * Collect companion files for a skill from built-in defaults, manifest files and
 * SKILL.md frontmatter. Files already inside the skill directory are skipped because
 * the bundle copy includes them.
 * Returns { files: [{ source, relPath, aliases }], missing: [relPath], warnings: [] }.
 */
export function collectCompanions(skill, sourceRoot) {
  const warnings = [];
  const rawEntries = [
    ...(BUILTIN_COMPANIONS[skill.id] ?? []),
    ...readManifestEntries(skill.dir, warnings),
    ...listFromKeys(skill.frontmatter),
  ];

  const files = new Map();
  const missing = [];
  for (const raw of rawEntries) {
    const relPath = toSafeRelative(raw);
    if (relPath === null) {
      if (raw && !URL_RE.test(String(raw))) {
        warnings.push(`Skipping unsafe companion path "${raw}" in ${skill.id}.`);
      }
      continue;
    }
    if (IGNORED_COMPANIONS.has(relPath)) {
      continue;
    }
    const located = locateCompanion(relPath, skill, sourceRoot);
    if (!located) {
      missing.push(relPath);
      continue;
    }
    if (isInside(skill.dir, located.source) || files.has(located.relPath)) {
      continue;
    }
    const aliases = COMPANION_ALIASES[located.relPath] ?? [];
    files.set(located.relPath, { ...located, aliases });
  }
  return { files: [...files.values()], missing: [...new Set(missing)], warnings };
}
