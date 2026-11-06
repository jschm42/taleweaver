# Agent Skills Installer (`taleweaver-skills`)

TaleWeaver ships with a standalone, dependency-free npm/npx-executable script that installs agent skills from `.claude/skills` and their companion documentation into target projects or agent directories.

---

## Quick Start

You can run the installer using `npx` from within the TaleWeaver repository root or directly if published:

```bash
# List available skills
npx . --list
# or via command name
npx taleweaver-skills --list
```

### Install a Specific Skill

```bash
# Install into another project directory (defaults to antigravity layout: <target>/.agents/skills/<skill>/)
npx taleweaver-skills taleweaver-adventure-concept-creator /path/to/my-project

# Install for Claude Code layout (<target>/.claude/skills/<skill>/)
npx taleweaver-skills taleweaver-adventure-concept-creator /path/to/my-project --format claude

# Install directly into a target folder without nested agent folders
npx taleweaver-skills taleweaver-adventure-concept-creator /path/to/my-skill-dir --format direct
```

### Install All Available Skills

```bash
npx taleweaver-skills --all /path/to/my-project
```

---

## Command Options

| Option | Shorthand | Description | Default |
|---|---|---|---|
| `--skill <name>` | `-s` | Name of the skill directory or frontmatter name to install | None |
| `--target <path>` | `-t`, `-d`, `--dest` | Destination directory | Current working directory (`.`) |
| `--all` | `-a` | Install all discovered skills | `false` |
| `--list` | `-l` | List all discovered skills with descriptions | `false` |
| `--format <type>` | `-f`, `--agent` | Directory layout (`antigravity`, `claude`, `direct`) | `antigravity` |
| `--dry-run` | | Simulate installation without writing files to disk | `false` |
| `--force` | | Overwrite existing files that differ from the packaged version | `false` |
| `--help` | `-h` | Display usage and help text | |
| `--version` | `-v` | Display package version | |

---

## Layouts & Companion Documents

### Layout Formats
- **`antigravity`** (default): Installs into `<target>/.agents/skills/<skill>/`.
- **`claude`**: Installs into `<target>/.claude/skills/<skill>/`.
- **`direct`**: Installs into `<target>/` (when installing a single skill) or `<target>/<skill>/` (when installing multiple skills).

### Companion Documentation
Skills may declare companion documentation via:
- Skill manifests (`manifest.json`, `skill.json`, `package.json` under `docs`, `files`, `companion_files`, `references`)
- `SKILL.md` frontmatter metadata
- Built-in mappings (e.g. for `taleweaver-adventure-concept-creator`):
  - `docs/world-builder-blueprint-manual.md`
  - `docs/world-builder-syntax.md`
  - `docs/scripting_engine.md` (and `docs/scripting-enginge.md` compatibility alias)
  - `docs/specs/adventure_format.md`

When installed into a project or fresh target directory:
1. Companion documentation files are copied into the skill bundle under `<skill_bundle>/docs/...`.
2. Companion documentation files are also mirrored to `<target>/docs/...` to maintain project-level references.
3. For single-skill installations into a fresh directory, `SKILL.md` is also mirrored to `<target>/SKILL.md` for toolchains expecting a flat single-skill folder.

---

## Testing

The installer comes with an extensive unit and end-to-end test suite built with Node's native test runner (`node:test`):

```bash
npm test
# or
node --test bin/test/installer.test.js
```
