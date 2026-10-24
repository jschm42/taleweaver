"""TaleWeaver Quality & Security Linter Runner.

Runs Ruff linter and formatter with focus on Clean Code, Cyclomatic Complexity,
and Security (Bandit). Supports staged-file checks for Git pre-commit hooks.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

MAX_FILE_LINES_WARNING = 600
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_command(cmd: list[str]) -> int:
    """Run a command in the project root directory and return its exit code."""
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
        return proc.returncode
    except Exception as exc:
        print(f"Error running command {' '.join(cmd)}: {exc}", file=sys.stderr)
        return 1


def get_staged_python_files() -> list[str]:
    """Retrieve staged Python files via Git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        files = [
            f.strip()
            for f in result.stdout.splitlines()
            if f.strip().endswith(".py") and os.path.exists(PROJECT_ROOT / f.strip())
        ]
        return files
    except Exception:
        return []


def get_changed_python_files(base_ref: str = "origin/main") -> list[str]:
    """Retrieve changed Python files against a base git reference."""
    diff_targets = [
        ["git", "diff", "--name-only", "--diff-filter=ACM", f"{base_ref}...HEAD"],
        ["git", "diff", "--name-only", "--diff-filter=ACM", f"{base_ref}..HEAD"],
        ["git", "diff", "--name-only", "--diff-filter=ACM", base_ref],
    ]
    for cmd in diff_targets:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            files = [
                f.strip()
                for f in result.stdout.splitlines()
                if f.strip().endswith(".py") and os.path.exists(PROJECT_ROOT / f.strip())
            ]
            if files:
                return files
    return []


def check_oversized_files(files: list[str]) -> list[tuple[str, int]]:
    """Identify files exceeding the recommended line threshold."""
    oversized: list[tuple[str, int]] = []
    for f in files:
        file_path = PROJECT_ROOT / f
        if not file_path.exists():
            continue
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as fp:
                line_count = sum(1 for _ in fp)
                if line_count > MAX_FILE_LINES_WARNING:
                    oversized.append((f, line_count))
        except OSError:
            continue
    return oversized


def main() -> int:
    parser = argparse.ArgumentParser(description="TaleWeaver Code Quality & Security Linter")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Only check files staged for git commit (pre-commit mode)",
    )
    parser.add_argument(
        "--changed",
        nargs="?",
        const="origin/main",
        metavar="BASE_REF",
        help="Only check Python files changed against base git ref (e.g. origin/main)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix fixable lint violations and format code",
    )
    parser.add_argument(
        "--format-only",
        action="store_true",
        help="Only format code without lint checks",
    )
    parser.add_argument(
        "--check-size",
        action="store_true",
        help="Scan and report modules exceeding the line threshold",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Specific files or directories to check",
    )

    args = parser.parse_args()

    # Ensure UTF-8 output where possible on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Determine targets
    if args.staged:
        targets = get_staged_python_files()
        if not targets:
            print("[INFO] No staged Python files to lint.")
            return 0
        print(f"[LINT] Checking {len(targets)} staged Python file(s)...")
    elif args.changed:
        targets = get_changed_python_files(args.changed)
        if not targets:
            print(f"[INFO] No changed Python files found against '{args.changed}'.")
            return 0
        print(f"[LINT] Checking {len(targets)} changed Python file(s) against '{args.changed}'...")
    elif args.paths:
        targets = args.paths
    else:
        targets = ["backend", "tests", "scripts"]

    ruff_cmd = [sys.executable, "-m", "ruff"]

    # 1. Format if requested, otherwise verify formatting
    if args.fix or args.format_only:
        print("[FORMAT] Formatting code with Ruff...")
        format_code = run_command([*ruff_cmd, "format", *targets])
        if args.format_only:
            return format_code
    else:
        print("[FORMAT] Checking code formatting with Ruff...")
        format_code = run_command([*ruff_cmd, "format", "--check", *targets])
        if format_code != 0:
            print(
                "[ERROR] Formatting check failed. Run 'poetry run python scripts/lint.py --fix' to format."
            )
            return format_code

    # 2. Run Ruff Linter
    print("[LINT] Running Ruff lint checks (Clean Code & Security)...")
    lint_args = [*ruff_cmd, "check"]
    if args.fix:
        lint_args.append("--fix")
    lint_args.extend(targets)

    exit_code = run_command(lint_args)

    # 3. Check for oversized modules
    if args.check_size or args.staged or args.changed:
        oversized = check_oversized_files(targets)
        if oversized:
            print("\n[WARN] [Clean Code Notice] Oversized modules detected (> 600 lines):")
            for path, count in oversized:
                print(f"   * {path}: {count} lines")
            print("   Consider decomposing large modules into dedicated service/handler classes.\n")

    if exit_code == 0:
        print("[OK] Clean Code & Security checks passed!")
    else:
        print("[ERROR] Linter detected issues. Please resolve before committing.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
