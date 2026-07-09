"""Integrator / orchestrator for the file-based multi-agent banking pipeline (serves M5).

Responsibilities:

* Create ``shared/{input,processing,output,results}/`` if absent.
* Load every record from ``sample-transactions.json``, wrap each in the standard message shape,
  and write it atomically into ``shared/input/``.
* Run the three cooperating agents **in order** -- validator -> fraud detector -> compliance
  checker -- for every transaction (in-process function calls).
* Tolerate malformed records: skip the bad record, write a synthetic ``malformed_input`` result,
  continue the batch, and report the parse-error count separately.
* Poll ``shared/results/`` until every input ``transaction_id`` has a terminal result (or timeout),
  then write and print ``shared/results/summary.json``.
* Idempotent: a second run reads existing results instead of recomputing and never duplicates.

``run_pipeline`` accepts an injectable ``shared_root`` so the integration test can point the whole
pipeline at an isolated ``tmp_path`` tree via the ``PIPELINE_SHARED_ROOT`` environment variable.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Make ``from agents import protocol`` work when run as ``python integrator.py``.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import protocol  # noqa: E402

AGENT_NAME = "integrator"
DEFAULT_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.05


# ---------------------------------------------------------------------------
# Record loading (malformed-tolerant)
# ---------------------------------------------------------------------------


def _split_top_level_objects(text: str) -> list[str]:
    """Split the top-level ``[...]`` array text into individual object substrings.

    Tolerant recovery path used only when strict ``json.load`` fails, so that a single malformed
    record does not abort parsing of its valid neighbours.
    """
    chunks: list[str] = []
    depth = 0
    in_str = False
    escape = False
    start: int | None = None
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                chunks.append(text[start : i + 1])
                start = None
    return chunks


def load_records(sample_file: str | Path) -> tuple[list[dict[str, Any]], int]:
    """Return ``(records, malformed_count)`` from ``sample_file``.

    Strict parse first; on failure, fall back to tolerant per-object recovery so valid records
    still flow through and each unrecoverable object is counted as ``malformed``.
    """
    path = Path(sample_file)
    raw = path.read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    malformed = 0
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]
        for item in parsed:
            if isinstance(item, dict) and str(item.get("transaction_id", "")).strip():
                records.append(item)
            else:
                malformed += 1
        return records, malformed
    except json.JSONDecodeError:
        pass

    # Tolerant recovery: parse each top-level object independently.
    for chunk in _split_top_level_objects(raw):
        try:
            item = json.loads(chunk)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(item, dict) and str(item.get("transaction_id", "")).strip():
            records.append(item)
        else:
            malformed += 1
    return records, malformed


def _write_malformed_result(index: int) -> str:
    """Write a synthetic rejected result for an unparseable record; return its synthetic id."""
    txn_id = f"MALFORMED-{index}"
    message = protocol.build_message(
        {
            "transaction_id": txn_id,
            "status": "rejected",
            "decision": "rejected",
            "reason": ["malformed_input"],
            "parse_error": True,
        },
        source_agent=AGENT_NAME,
        target_agent=AGENT_NAME,
        message_type="result",
    )
    protocol.write_result(message)
    protocol.audit_log(AGENT_NAME, txn_id, "rejected", extra={"parse_error": True})
    return txn_id


# ---------------------------------------------------------------------------
# Per-transaction pipeline (validator -> fraud -> compliance)
# ---------------------------------------------------------------------------


def process_transaction(message: dict[str, Any]) -> dict[str, Any]:
    """Run one message through the three pipeline agents, in the order resolved by
    ``agents.rule_engine.determine_pipeline_order`` -- by default validator -> fraud detector ->
    compliance checker, but a caller may request a different order via ``data.pipeline_order`` (see
    M6 / the Rule Engine task in ``specification.md``).

    The resolved order is stamped onto ``data.pipeline_order_used`` before any agent runs, and each
    agent is called with ``next_agent`` set to the following stage in that order (or ``None`` for
    the last stage), so whichever agent runs last is the one that writes the terminal result.

    Idempotent: if a terminal result already exists for the ``transaction_id`` it is returned
    unchanged (the agents also self-guard). Returns the final result message.
    """
    from agents import transaction_validator, fraud_detector, compliance_checker, rule_engine

    txn_id = protocol.transaction_id_of(message)
    if txn_id and protocol.result_exists(txn_id):
        protocol.audit_log(AGENT_NAME, txn_id, "duplicate_ignored")
        return protocol.read_result(txn_id) or message

    data = message.get("data")
    if not isinstance(data, dict):
        data = {}
        message["data"] = data

    # Effective idempotency/result key, mirroring protocol.write_result's own fallback so an early
    # exit is detected correctly even for a message with a missing/blank transaction_id.
    effective_id = txn_id or str(message.get("message_id") or "")

    order = rule_engine.determine_pipeline_order(
        requested_order=data.get("pipeline_order"), transaction_id=txn_id or None
    )
    data["pipeline_order_used"] = order

    agent_funcs = {
        "transaction_validator": transaction_validator.process_message,
        "fraud_detector": fraud_detector.process_message,
        "compliance_checker": compliance_checker.process_message,
    }

    current = message
    for index, agent_name in enumerate(order):
        next_agent = order[index + 1] if index + 1 < len(order) else None
        current = agent_funcs[agent_name](current, next_agent=next_agent)
        if effective_id and protocol.result_exists(effective_id):
            # A terminal result now exists -- either this was the last stage, or an earlier stage
            # (rejection / fail-closed error) short-circuited the rest of the run.
            break

    return protocol.read_result(txn_id) or current


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def build_summary(malformed_count: int) -> dict[str, Any]:
    """Aggregate counts across every file currently in ``shared/results/``."""
    summary = {
        "total": 0,
        "validated": 0,
        "rejected_at_validation": 0,
        "cleared": 0,
        "flagged": 0,
        "rejected_at_compliance": 0,
        "requires_report": 0,
        "malformed_input_count": malformed_count,
        "error_count": 0,
        "generated_at": protocol.iso_now(),
    }
    for path in protocol.list_messages("results"):
        if path.name == "summary.json":
            continue
        try:
            msg = protocol.read_message(path)
        except ValueError:
            continue
        data = msg.get("data") or {}
        summary["total"] += 1
        status = data.get("status")
        decision = data.get("decision")
        reason = data.get("reason")
        reasons = reason if isinstance(reason, list) else ([reason] if reason else [])

        if data.get("requires_report"):
            summary["requires_report"] += 1
        if status == "error" or decision == "error":
            summary["error_count"] += 1

        if status == "rejected" and decision not in {"cleared", "flagged", "rejected"}:
            # Rejected before reaching compliance (validator / malformed).
            summary["rejected_at_validation"] += 1
            continue

        # Reached compliance -> counts as validated.
        if decision in {"cleared", "flagged", "rejected"}:
            summary["validated"] += 1
            if decision == "cleared":
                summary["cleared"] += 1
            elif decision == "flagged":
                summary["flagged"] += 1
            elif decision == "rejected":
                if "blocked_account" in reasons or any(
                    str(r).startswith("missing_regulated_field") for r in reasons
                ):
                    summary["rejected_at_compliance"] += 1
                else:
                    summary["rejected_at_compliance"] += 1
        elif status == "rejected":
            summary["rejected_at_validation"] += 1
    return summary


def _write_summary(summary: dict[str, Any]) -> Path:
    path = protocol.shared_subdir("results") / "summary.json"
    from agents.protocol import _atomic_write_json  # local import: internal helper

    return _atomic_write_json(path, summary)


# ---------------------------------------------------------------------------
# Orchestration entrypoint
# ---------------------------------------------------------------------------


def run_pipeline(
    sample_file: str = "sample-transactions.json",
    *,
    shared_root: str | Path | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Drive every record in ``sample_file`` to a terminal result and return the summary dict."""
    if shared_root is not None:
        os.environ["PIPELINE_SHARED_ROOT"] = str(Path(shared_root).resolve())

    protocol.ensure_dirs()
    protocol.audit_log(AGENT_NAME, "-", "pipeline_start", extra={"sample_file": str(sample_file)})

    records, malformed_count = load_records(sample_file)
    for i in range(malformed_count):
        _write_malformed_result(i + 1)

    expected_ids: list[str] = []
    for record in records:
        txn_id = str(record.get("transaction_id"))
        expected_ids.append(txn_id)
        message = protocol.build_message(
            dict(record),
            source_agent=AGENT_NAME,
            target_agent="transaction_validator",
            message_type="transaction",
        )
        protocol.write_message(message, "input")

    # Process each transaction in order through the three agents.
    for txn_id in expected_ids:
        input_path = protocol.shared_subdir("input") / f"{protocol._safe_name(txn_id)}.json"
        try:
            message = protocol.read_message(input_path)
        except (ValueError, OSError):
            message = None
        if message is None:
            continue
        try:
            process_transaction(message)
        except Exception as exc:  # fail-closed: hold for manual review, never silently drop
            protocol.audit_log(
                AGENT_NAME, txn_id, "error", extra={"error_type": type(exc).__name__}
            )
            protocol.write_result(
                protocol.build_message(
                    {
                        "transaction_id": txn_id,
                        "status": "error",
                        "decision": "error",
                        "reason": ["pipeline_error"],
                    },
                    source_agent=AGENT_NAME,
                    target_agent=AGENT_NAME,
                    message_type="result",
                )
            )

    # Poll results until every expected id (plus malformed synthetics) is terminal.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(protocol.result_exists(tid) for tid in expected_ids):
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    summary = build_summary(malformed_count)
    _write_summary(summary)
    protocol.audit_log(AGENT_NAME, "-", "pipeline_end", extra={"total": summary["total"]})
    return summary


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    sample_file = "sample-transactions.json"
    for i, arg in enumerate(argv):
        if arg in ("--sample", "--sample-file") and i + 1 < len(argv):
            sample_file = argv[i + 1]
        elif arg.startswith("--sample="):
            sample_file = arg.split("=", 1)[1]

    summary = run_pipeline(sample_file)
    print("\n=== Banking Pipeline Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nResults written to: {protocol.shared_subdir('results')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
