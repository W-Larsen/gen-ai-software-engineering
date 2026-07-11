"""Custom FastMCP server that makes the banking pipeline queryable (Task 4).

Exposes a thin, **read-only** query layer over the pipeline's terminal outcomes in
``shared/results/`` -- no pipeline logic is duplicated. All file access goes through
``agents.protocol`` so the shared/ root honours ``PIPELINE_SHARED_ROOT`` exactly like the rest of
the pipeline (and so tests can point it at an isolated tree).

Surface (per TASKS.md Task 4):

* Tool ``get_transaction_status(transaction_id)`` -> current status for one transaction.
* Tool ``list_pipeline_results()``               -> summary of every processed transaction.
* Resource ``pipeline://summary``                -> the latest run summary as text.

The MCP business logic lives in plain ``_helper`` functions; the decorated tools/resource are thin
wrappers over them so they can be unit-tested without standing up the stdio transport.

Run standalone (as ``mcp.json`` invokes it)::

    python mcp/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# --- bootstrap: make the sibling ``agents``/``frontend`` packages importable when this file is run
# as ``python mcp/server.py`` (mirrors integrator.py). Repo root goes on sys.path; the installed
# ``mcp`` SDK is a *regular* package (has __init__.py) so it still wins over the __init__-less local
# ``mcp/`` directory during ``from mcp.server.fastmcp import FastMCP``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Apply the Python 3.14rc compat shim BEFORE importing FastMCP (which pulls in pydantic).
import frontend._py314_compat  # noqa: E402,F401  (import applies the shim on import)

from mcp.server.fastmcp import FastMCP  # noqa: E402

from agents import protocol  # noqa: E402

# Fields that are safe to surface over MCP. Account numbers, holder names, and free-text
# descriptions are deliberately omitted to honour the pipeline's no-plaintext-PII principle.
_PUBLIC_FIELDS: tuple[str, ...] = (
    "transaction_id",
    "status",
    "decision",
    "reason",
    "risk_score",
    "requires_report",
    "fraud_review",
    "fraud_signals",
    "currency",
    "timestamp",
)

mcp = FastMCP("pipeline-status")


# ---------------------------------------------------------------------------
# Plain helpers (unit-testable without the MCP transport)
# ---------------------------------------------------------------------------


def _public_view(data: dict[str, Any]) -> dict[str, Any]:
    """Project a result's ``data`` payload down to the PII-safe public fields."""
    return {field: data[field] for field in _PUBLIC_FIELDS if field in data}


def _status_for(transaction_id: str) -> dict[str, Any]:
    """Return the current status for one transaction from ``shared/results/``.

    ``{"transaction_id": id, "found": false}`` when no terminal result exists yet.
    """
    txn_id = str(transaction_id).strip()
    result = protocol.read_result(txn_id) if txn_id else None
    if result is None:
        return {"transaction_id": txn_id, "found": False}
    view = _public_view(result.get("data") or {})
    view.setdefault("transaction_id", txn_id)
    view["found"] = True
    return view


def _all_results() -> dict[str, Any]:
    """Summarise every processed transaction currently in ``shared/results/``."""
    transactions: list[dict[str, Any]] = []
    by_decision: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for path in protocol.list_messages("results"):
        if path.name == "summary.json":
            continue
        try:
            message = protocol.read_message(path)
        except ValueError:
            continue
        data = message.get("data") or {}
        transactions.append(_public_view(data))
        decision = str(data.get("decision", "unknown"))
        status = str(data.get("status", "unknown"))
        by_decision[decision] = by_decision.get(decision, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1

    transactions.sort(key=lambda t: str(t.get("transaction_id", "")))
    return {
        "total": len(transactions),
        "by_decision": by_decision,
        "by_status": by_status,
        "transactions": transactions,
        "generated_at": protocol.iso_now(),
    }


def _summary_text() -> str:
    """Return the latest pipeline run summary as text.

    Reads ``shared/results/summary.json`` when present; otherwise falls back to counts computed
    from the current result files. Never raises -- always returns a human-readable string.
    """
    summary_path = protocol.shared_subdir("results") / "summary.json"
    if summary_path.exists():
        try:
            summary = protocol.read_message(summary_path)
            return json.dumps(summary, indent=2, sort_keys=True)
        except ValueError:
            pass  # fall through to a computed summary

    computed = _all_results()
    header = "summary.json not found -- computed from current results in shared/results/"
    return header + "\n" + json.dumps(computed, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# MCP surface (thin wrappers over the helpers above)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_transaction_status(transaction_id: str) -> dict[str, Any]:
    """Return the current pipeline status for a single transaction id."""
    return _status_for(transaction_id)


@mcp.tool()
def list_pipeline_results() -> dict[str, Any]:
    """Return a summary of all processed transactions (counts + per-transaction status)."""
    return _all_results()


@mcp.resource("pipeline://summary")
def pipeline_summary() -> str:
    """Return the latest pipeline run summary as text."""
    return _summary_text()


if __name__ == "__main__":
    mcp.run()
