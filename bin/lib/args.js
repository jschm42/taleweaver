// Command-line argument parsing for the skill installer (no external dependencies).

export const FORMATS = ['antigravity', 'claude', 'direct'];

export class UsageError extends Error {}

const VALUE_FLAGS = {
  '-s': 'skill',
  '--skill': 'skill',
  '-t': 'target',
  '--target': 'target',
  '-d': 'target',
  '--dest': 'target',
  '-f': 'format',
  '--format': 'format',
  '--agent': 'format',
};

const BOOLEAN_FLAGS = {
  '-a': 'all',
  '--all': 'all',
  '-l': 'list',
  '--list': 'list',
  '--dry-run': 'dryRun',
  '--force': 'force',
  '-h': 'help',
  '--help': 'help',
  '-v': 'version',
  '--version': 'version',
};

function splitInlineValue(token) {
  const eq = token.indexOf('=');
  if (!token.startsWith('--') || eq === -1) {
    return [token, undefined];
  }
  return [token.slice(0, eq), token.slice(eq + 1)];
}

function readFlagValue(flag, inlineValue, argv, index) {
  if (inlineValue !== undefined) {
    return { value: inlineValue, consumed: 0 };
  }
  const next = argv[index + 1];
  if (next === undefined || (next.startsWith('-') && next !== '-')) {
    throw new UsageError(`Option ${flag} requires a value.`);
  }
  return { value: next, consumed: 1 };
}

function tokenize(argv) {
  const options = {};
  const positionals = [];
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--') {
      positionals.push(...argv.slice(i + 1));
      break;
    }
    if (!token.startsWith('-') || token === '-') {
      positionals.push(token);
      continue;
    }
    const [flag, inlineValue] = splitInlineValue(token);
    if (BOOLEAN_FLAGS[flag]) {
      if (inlineValue !== undefined) {
        throw new UsageError(`Option ${flag} does not take a value.`);
      }
      options[BOOLEAN_FLAGS[flag]] = true;
      continue;
    }
    if (!VALUE_FLAGS[flag]) {
      throw new UsageError(`Unknown option: ${flag}`);
    }
    const { value, consumed } = readFlagValue(flag, inlineValue, argv, i);
    options[VALUE_FLAGS[flag]] = value;
    i += consumed;
  }
  return { options, positionals };
}

function normalizeFormat(raw) {
  const format = String(raw ?? 'antigravity')
    .trim()
    .toLowerCase();
  if (!FORMATS.includes(format)) {
    throw new UsageError(`Unknown format "${raw}". Expected one of: ${FORMATS.join(', ')}.`);
  }
  return format;
}

/**
 * Parse argv (without the node binary and script path) into installer options.
 * Positional form: [skill-name] [target-dir]; with --all a single positional is the target.
 */
export function parseArgs(argv) {
  const { options, positionals } = tokenize(argv);
  const rest = [...positionals];

  if (options.all && options.skill) {
    throw new UsageError('Use either --skill <name> or --all, not both.');
  }
  const skill = options.all ? undefined : (options.skill ?? rest.shift());
  const target = options.target ?? rest.shift();
  if (rest.length > 0) {
    throw new UsageError(`Unexpected argument(s): ${rest.join(' ')}`);
  }
  if (target !== undefined && target.trim() === '') {
    throw new UsageError('Target directory must not be empty.');
  }

  return {
    skill,
    target,
    all: Boolean(options.all),
    list: Boolean(options.list),
    format: normalizeFormat(options.format),
    dryRun: Boolean(options.dryRun),
    force: Boolean(options.force),
    help: Boolean(options.help),
    version: Boolean(options.version),
  };
}
