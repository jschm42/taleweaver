#!/usr/bin/env node
// Installs TaleWeaver agent skills (.agents/skills/<skill>) plus their companion docs
// into another project or directory. Uses only the Node.js standard library.

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import readline from 'node:readline/promises';
import { fileURLToPath } from 'node:url';

import { parseArgs, UsageError, FORMATS } from './lib/args.js';
import { buildPlan, executePlan, inspectTarget } from './lib/plan.js';
import {
  collectCompanions,
  discoverSkills,
  findSkill,
  resolveSkillsRoot,
  SKILLS_SUBDIR,
} from './lib/skills.js';

const EXIT_OK = 0;
const EXIT_FAILURE = 1;
const EXIT_USAGE = 2;

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const COMMAND = 'taleweaver-skills';

const HELP = `Usage:
  ${COMMAND} [skill-name] [target-dir] [options]
  ${COMMAND} --all [target-dir] [options]
  ${COMMAND} --list

Installs TaleWeaver agent skills and their companion docs into a directory.

Options:
  -s, --skill <name>          Skill to install (directory name or frontmatter name)
  -t, --target <path>         Target directory (default: current directory)
  -d, --dest <path>           Alias for --target
  -a, --all                   Install all available skills
  -l, --list                  List available skills with descriptions
  -f, --format <type>         Layout: ${FORMATS.join(', ')} (default: antigravity)
      --agent <type>          Alias for --format
      --dry-run               Show what would be written without writing
      --force                 Overwrite files that differ from the packaged version
  -h, --help                  Show this help
  -v, --version               Show the installer version

Layouts:
  antigravity   <target>/.agents/skills/<skill>/
  claude        <target>/.claude/skills/<skill>/
  direct        <target>/ (one skill) or <target>/<skill>/ (several skills)

Companion docs are copied into the skill bundle and, for project or fresh
targets, also to <target>/docs/. Fresh targets additionally get
.agents/skills/<skill>/ and a top-level SKILL.md (single-skill installs).

Exit codes: 0 success, 1 failure or conflicts, 2 usage error.

Examples:
  npx ${COMMAND} --list
  npx ${COMMAND} taleweaver-adventure-concept-creator ./my-project
  npx ${COMMAND} --all --format claude --target ~/work/app --dry-run`;

function readVersion() {
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8'));
    return pkg.version ?? 'unknown';
  } catch {
    return 'unknown';
  }
}

function loadSkills() {
  const roots = [...new Set([PACKAGE_ROOT, process.cwd()])];
  const located = resolveSkillsRoot(roots);
  if (!located) {
    throw new Error(`No ${SKILLS_SUBDIR} directory found in: ${roots.join(', ')}`);
  }
  const skills = discoverSkills(located.skillsDir);
  if (skills.length === 0) {
    throw new Error(`No skills (directories with SKILL.md) found in ${located.skillsDir}`);
  }
  return { ...located, skills };
}

function printList(skills, skillsDir) {
  console.log(`Available skills (${skills.length}) from ${skillsDir}:\n`);
  for (const skill of skills) {
    const alias = skill.name === skill.id ? '' : ` (name: ${skill.name})`;
    console.log(`  ${skill.id}${alias}`);
    console.log(`      ${skill.description || 'No description.'}\n`);
  }
}

async function promptForSkill(skills) {
  console.log('Select a skill to install:\n');
  skills.forEach((skill, index) => console.log(`  ${index + 1}) ${skill.id}`));
  console.log(`  a) all skills\n`);
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = (await rl.question('Choice: ')).trim().toLowerCase();
    if (answer === 'a' || answer === 'all') {
      return skills;
    }
    const picked = skills[Number.parseInt(answer, 10) - 1] ?? findSkill(skills, answer);
    if (!picked) {
      throw new UsageError(`Invalid choice: "${answer}"`);
    }
    return [picked];
  } finally {
    rl.close();
  }
}

async function selectSkills(options, skills) {
  if (options.all) {
    return skills;
  }
  if (options.skill) {
    const skill = findSkill(skills, options.skill);
    if (!skill) {
      const names = skills.map((s) => s.id).join(', ');
      throw new UsageError(`Unknown skill "${options.skill}". Available: ${names}`);
    }
    return [skill];
  }
  if (!process.stdin.isTTY) {
    throw new UsageError('No skill given. Pass a skill name, --skill <name> or --all.');
  }
  return promptForSkill(skills);
}

function relativeToTarget(target, file) {
  return path.relative(target, file) || '.';
}

function reportPlan(plan, ctx, dryRun) {
  const prefix = dryRun ? '[dry-run] ' : '';
  const labels = {
    create: 'create   ',
    overwrite: 'overwrite',
    unchanged: 'unchanged',
    conflict: 'conflict ',
  };
  for (const op of plan) {
    const label = op.blocked ? 'skip     ' : labels[op.status];
    console.log(`${prefix}${label} ${relativeToTarget(ctx.target, op.dest)}`);
  }
}

function summarize(plan) {
  const count = (predicate) => plan.filter(predicate).length;
  return {
    create: count((op) => op.status === 'create'),
    overwrite: count((op) => op.status === 'overwrite' && !op.blocked),
    unchanged: count((op) => op.status === 'unchanged'),
    blocked: plan.filter((op) => op.blocked),
  };
}

function reportBlocked(blocked, target) {
  console.error(`\n${blocked.length} file(s) already exist with different content:`);
  for (const op of blocked) {
    const reason = op.status === 'conflict' ? ' (not a regular file)' : '';
    console.error(`  ${relativeToTarget(target, op.dest)}${reason}`);
  }
  console.error('Nothing was written. Re-run with --force to overwrite them.');
}

function prepareEntries(selected, sourceRoot, warnings) {
  return selected.map((skill) => {
    const companions = collectCompanions(skill, sourceRoot);
    warnings.push(...companions.warnings);
    companions.missing.forEach((rel) => warnings.push(`Companion file not found for ${skill.id}: ${rel}`));
    return { skill, companions };
  });
}

async function install(options) {
  const { sourceRoot, skills } = loadSkills();
  const selected = await selectSkills(options, skills);
  const target = path.resolve(options.target ?? process.cwd());
  const ctx = {
    ...inspectTarget(target),
    target,
    format: options.format,
    multi: selected.length > 1,
    force: options.force,
    warnings: [],
  };

  const entries = prepareEntries(selected, sourceRoot, ctx.warnings);
  const plan = buildPlan(ctx, entries);
  const kind = ctx.fresh ? 'fresh directory' : ctx.project ? 'project' : 'existing directory';

  console.log(`Installing ${selected.map((s) => s.id).join(', ')}`);
  console.log(`  target: ${target} (${kind})`);
  console.log(`  format: ${ctx.format}\n`);
  ctx.warnings.forEach((warning) => console.warn(`warning: ${warning}`));
  reportPlan(plan, ctx, options.dryRun);

  const summary = summarize(plan);
  if (summary.blocked.length > 0) {
    reportBlocked(summary.blocked, target);
    return EXIT_FAILURE;
  }
  const totals = `${summary.create} new, ${summary.overwrite} overwritten, ${summary.unchanged} unchanged`;
  if (options.dryRun) {
    console.log(`\nDry run complete: ${totals}. No files were written.`);
    return EXIT_OK;
  }
  const written = executePlan(plan);
  console.log(`\nDone: ${written} file(s) written (${totals}).`);
  return EXIT_OK;
}

async function main(argv) {
  const options = parseArgs(argv);
  if (options.help) {
    console.log(HELP);
    return EXIT_OK;
  }
  if (options.version) {
    console.log(`${COMMAND} ${readVersion()}`);
    return EXIT_OK;
  }
  if (options.list) {
    const { skills, skillsDir } = loadSkills();
    printList(skills, skillsDir);
    return EXIT_OK;
  }
  return install(options);
}

main(process.argv.slice(2))
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    const usage = error instanceof UsageError;
    console.error(`error: ${error.message}`);
    if (usage) {
      console.error(`Run "${COMMAND} --help" for usage.`);
    }
    process.exitCode = usage ? EXIT_USAGE : EXIT_FAILURE;
  });
