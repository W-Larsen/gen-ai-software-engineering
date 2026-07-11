#!/usr/bin/env python3
"""PostToolUse(Bash) audit-log hook for the homework-6 banking pipeline.

Appends one ISO-8601 line to ``logs/audit.log`` whenever a Bash command runs the pipeline
(``integrator.py``), the validator, or the test suite (``pytest``). It is purely observational:
it **never** blocks a tool call and always exits ``0``.

Line format:  ``<iso8601>\thook\tpost_bash\t<kind>\texit=<code>``
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# .../homework-6/.claude/hooks/audit_log.py -> parents[2] == homework-6/
PROJECT_DIR = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_DIR / "logs"


def _classify(command: str) -> str | None:
    """Return a short label for pipeline-relevant commands, or None to skip logging."""
    c = (command or "").lower()
    if "integrator.py" in c:
        return "pipeline_run"
    if "transaction_validator.py" in c:
        return "validate"
    if "pytest" in c:
        return "tests"
    return None


def _exit_code(payload: dict) -> str:
    """Best-effort extraction of the command's exit code from the tool response."""
    resp = payload.get("tool_response")
    if isinstance(resp, dict):
        for key in ("exit_code", "exitCode", "returncode", "code"):
            if key in resp and resp[key] is not None:
                return str(resp[key])
    return "?"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    kind = _classify(command)
    if kind is None:
        return 0  # not pipeline-relevant -> nothing to record

    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts}\thook\tpost_bash\t{kind}\texit={_exit_code(payload)}\n"
        with (LOGS_DIR / "audit.log").open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        # Auditing is best-effort; never let a logging failure disrupt the session.
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
