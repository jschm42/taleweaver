// Builds and executes the list of file copies for a skill installation.

import fs from 'node:fs';
import path from 'node:path';

import { SKILL_FILE, SKILLS_SUBDIR } from './skills.js';

const FORMAT_DIRS = {
  antigravity: SKILLS_SUBDIR,
  claude: path.join('.claude', 'skills'),
};
const PROJECT_MARKERS = ['.git', '.agents', '.claude', 'package.json', 'pyproject.toml'];
const IGNORED_NAMES = new Set(['.DS_Store', 'Thumbs.db', 'node_modules', '__pycache__', '.git']);

/** Describe the target directory: { exists, fresh, project }. */
export function inspectTarget(target) {
  if (!fs.existsSync(target)) {
    return { exists: false, fresh: true, project: false };
  }
  if (!fs.statSync(target).isDirectory()) {
    throw new Error(`Target exists and is not a directory: ${target}`);
  }
  const entries = fs.readdirSync(target);
  const project = PROJECT_MARKERS.some((marker) => entries.includes(marker));
  return { exists: true, fresh: entries.length === 0, project };
}

function walkFiles(dir, warnings, prefix = '') {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (IGNORED_NAMES.has(entry.name)) {
      continue;
    }
    const rel = prefix ? path.join(prefix, entry.name) : entry.name;
    const full = path.join(dir, entry.name);
    if (entry.isSymbolicLink()) {
      warnings.push(`Skipping symbolic link ${full}`);
      continue;
    }
    if (entry.isDirectory()) {
      results.push(...walkFiles(full, warnings, rel));
      continue;
    }
    if (entry.isFile()) {
      results.push(rel);
    }
  }
  return results;
}

function primaryBundleDir(ctx, skillId) {
  if (ctx.format === 'direct') {
    return ctx.multi ? path.join(ctx.target, skillId) : ctx.target;
  }
  return path.join(ctx.target, FORMAT_DIRS[ctx.format], skillId);
}

/**
 * Directories that receive the full skill bundle. A fresh target always gets the
 * project layout (.agents/skills/<skill>) in addition to the chosen format, so
 * checks expecting either a project or a flat structure find the skill.
 */
function bundleDirs(ctx, skillId) {
  const dirs = [primaryBundleDir(ctx, skillId)];
  if (ctx.fresh) {
    dirs.push(path.join(ctx.target, SKILLS_SUBDIR, skillId));
  }
  return [...new Set(dirs)];
}

function companionTargets(file) {
  return [file.relPath, ...file.aliases].map((rel) => rel.split('/').join(path.sep));
}

function planSkill(ctx, skill, companions) {
  const ops = [];
  const add = (source, dest) => ops.push({ source, dest, skill: skill.id });
  const skillFiles = walkFiles(skill.dir, ctx.warnings);

  for (const bundle of bundleDirs(ctx, skill.id)) {
    skillFiles.forEach((rel) => add(path.join(skill.dir, rel), path.join(bundle, rel)));
    for (const file of companions.files) {
      companionTargets(file).forEach((rel) => add(file.source, path.join(bundle, rel)));
    }
  }

  if (ctx.fresh || ctx.project) {
    for (const file of companions.files) {
      companionTargets(file).forEach((rel) => add(file.source, path.join(ctx.target, rel)));
    }
  }

  const flatSkillFile = path.join(ctx.target, SKILL_FILE);
  if (ctx.fresh && !ctx.multi) {
    add(path.join(skill.dir, SKILL_FILE), flatSkillFile);
  }
  return ops;
}

function assertInsideTarget(target, dest) {
  const rel = path.relative(target, dest);
  if (rel === '' || rel.startsWith('..') || path.isAbsolute(rel)) {
    throw new Error(`Refusing to write outside the target directory: ${dest}`);
  }
}

function classify(op) {
  if (!fs.existsSync(op.dest)) {
    return 'create';
  }
  if (!fs.statSync(op.dest).isFile()) {
    return 'conflict';
  }
  const same = fs.readFileSync(op.source).equals(fs.readFileSync(op.dest));
  return same ? 'unchanged' : 'overwrite';
}

/**
 * Build the de-duplicated copy plan for all selected skills.
 * ctx: { target, format, multi, fresh, project, force, warnings }
 * entries: [{ skill, companions }]
 */
export function buildPlan(ctx, entries) {
  const byDest = new Map();
  for (const { skill, companions } of entries) {
    for (const op of planSkill(ctx, skill, companions)) {
      assertInsideTarget(ctx.target, op.dest);
      if (!byDest.has(op.dest)) {
        byDest.set(op.dest, op);
      }
    }
  }
  return [...byDest.values()].map((op) => {
    const status = classify(op);
    const blocked = status === 'conflict' || (status === 'overwrite' && !ctx.force);
    return { ...op, status, blocked };
  });
}

/** Copy every non-blocked, changed file. Returns the number of files written. */
export function executePlan(plan) {
  let written = 0;
  for (const op of plan) {
    if (op.blocked || op.status === 'unchanged') {
      continue;
    }
    fs.mkdirSync(path.dirname(op.dest), { recursive: true });
    fs.copyFileSync(op.source, op.dest);
    written += 1;
  }
  return written;
}
