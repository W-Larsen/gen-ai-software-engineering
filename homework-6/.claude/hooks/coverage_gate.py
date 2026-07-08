#!/usr/bin/env python3
"""PreToolUse(Bash) coverage-gate hook for the homework-6 banking pipeline.

Blocks any ``git push`` when unit-test coverage over ``agents`` + ``integrator`` is below 80%.

Contract (Claude Code PreToolUse hooks):
* Hook input is a JSON object on **stdin**; the Bash command is at ``tool_input.command``.
* Exit ``0``  -> allow the tool call.
* Exit ``2``  -> **deny** the tool call; stderr is shown to Claude as the reason.
* Any other non-zero exit is treated as a non-blocking hook error.

The gate is a no-op for every command that is not a ``git push`` so it never slows unrelated work.
It is pure Python (no shell-isms) and resolves the project directory from its own location, so it
behaves identically on Windows and POSIX.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

# .../homework-6/.claude/hooks/coverage_gate.py -> parents[2] == homework-6/
PROJECT_DIR = Path(__file__).resolve().parents[2]
COVERAGE_THRESHOLD = 80


def _is_git_push(command: str) -> bool:
    """True only when the command actually invokes ``git ... push`` as a subcommand.

    Tokenizing with ``shlex`` means ``push`` appearing *inside a quoted argument* (e.g. a
    ``git commit -m "...git push..."`` message) is a single token and does not match -- only a
    bare ``push`` token following a bare ``git`` token counts. This avoids blocking commits or
    echoes that merely mention the phrase.
    """
    try:
        tokens = shlex.split(command or "", posix=True)
    except ValueError:
        tokens = (command or "").split()
    seen_git = False
    for token in tokens:
        if token == "git":
            seen_git = True
        elif token == "push" and seen_git:
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # No parseable input -> nothing to gate on. Do not block.
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not _is_git_push(command):
        return 0  # not a push -> allow, no-op

    # Run the coverage gate. pytest exits non-zero on either failing tests or coverage < threshold.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--cov=agents",
            "--cov=integrator",
            "--cov-report=term-missing",
            f"--cov-fail-under={COVERAGE_THRESHOLD}",
        ],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )

    if proc.returncode == 0:
        return 0  # coverage >= threshold and tests pass -> allow the push

    # Blocked. Surface the tail of pytest output (which includes the coverage total / TOTAL row and
    # the "Required test coverage of 80% not reached" line) as the denial reason.
    tail = (proc.stdout or "") + (proc.stderr or "")
    tail_lines = tail.strip().splitlines()[-25:]
    sys.stderr.write(
        f"Push blocked by coverage gate: unit-test coverage must be >= {COVERAGE_THRESHOLD}% "
        "(over agents + integrator) and all tests must pass before pushing.\n"
        "Run: python -m pytest tests/ --cov=agents --cov=integrator --cov-report=term-missing\n\n"
        + "\n".join(tail_lines)
        + "\n"
    )
    return 2  # PreToolUse deny


if __name__ == "__main__":
    raise SystemExit(main())
