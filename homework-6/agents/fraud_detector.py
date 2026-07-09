"""Fraud Detector agent for the banking transaction-processing pipeline (serves M2).

Implements ``process_message(message: dict) -> dict`` per ``specification.md`` (Task: Fraud
Detector). The fraud detector is the second stage of the pipeline: it reads a *validated* message
handed off by ``agents.transaction_validator`` (status == "validated") and computes a
deterministic, bounded ``[0, 100]`` risk score from three documented signals -- high value,
off-hours timing, and cross-border indicator. Fraud is a **signal, not a hard reject**: every
transaction is forwarded to the compliance checker via ``shared/output/`` carrying its score,
flag, and the list of triggered signal names; nothing is rejected here.

This module reuses ``agents.protocol`` for the message envelope, atomic file I/O, Decimal/
timestamp parsing, idempotency checks, and PII-masked audit logging -- it does not reimplement any
of that. Score weights and thresholds are *named constants sourced from
``agents/config/fraud_rules.json``*, not inline literals, so ops/compliance can retune them
without a code change (see ``specification.md`` "Configuration over hardcoding").

Scoring assumption (documented, see ``specification.md`` "Assumptions & Open Questions"): no live
FX-rate feed exists in v1, so the high-value threshold is compared directly against the
transaction's *stated-currency* amount without conversion.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agents import protocol

AGENT_NAME = "fraud_detector"

_CONFIG_PATH = protocol.get_repo_root() / "agents" / "config" / "fraud_rules.json"

# Names of the three documented risk signals, in evaluation order. Used both as the values placed
# in the outgoing message's ``fraud_signals`` list and as keys into the loaded rules dict.
SIGNAL_HIGH_VALUE = "high_value"
SIGNAL_OFF_HOURS = "off_hours"
SIGNAL_CROSS_BORDER = "cross_border"


def load_rules(path: pathlib.Path | str | None = None) -> dict[str, Any]:
    """Load fraud-scoring weights/thresholds from ``agents/config/fraud_rules.json``.

    Named constants (threshold, off-hours window, home-country set, score weights) are sourced
    from this versioned config file rather than hardcoded as inline literals in the scoring logic,
    per the spec's "Configuration over hardcoding" implementation note. The monetary threshold is
    parsed via ``protocol.to_decimal`` so it participates in ``Decimal``-only comparisons.
    """
    cfg_path = pathlib.Path(path) if path else _CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {
        "high_value_threshold": protocol.to_decimal(raw["high_value_threshold"]),
        "high_value_score": int(raw["high_value_score"]),
        "off_hours_start_hour": int(raw["off_hours_start_hour"]),
        "off_hours_end_hour": int(raw["off_hours_end_hour"]),
        "off_hours_score": int(raw["off_hours_score"]),
        "cross_border_score": int(raw["cross_border_score"]),
        "home_countries": frozenset(str(c).strip().upper() for c in raw["home_countries"]),
        "fraud_review_threshold": int(raw["fraud_review_threshold"]),
    }


# Loaded once at import time; ``load_rules()`` remains available for tests that want to exercise
# an alternate/synthetic config file.
RULES: dict[str, Any] = load_rules()


def score_transaction(data: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """Pure, deterministic fraud-risk scoring function -- **no file I/O, no logging**.

    Sums three documented signals (weights sourced from ``rules``, e.g. ``load_rules()``):

    * ``high_value``    (+``rules["high_value_score"]``) when the transaction's canonical
      ``amount`` is ``>= rules["high_value_threshold"]`` in the transaction's *stated* currency
      (no live FX conversion -- documented assumption). Strict ``>=`` means the boundary amount
      ``Decimal("9999.99")`` (TXN003) never triggers this signal.
    * ``off_hours``     (+``rules["off_hours_score"]``) when the transaction timestamp's UTC hour
      falls in ``[rules["off_hours_start_hour"], rules["off_hours_end_hour"])``.
    * ``cross_border``  (+``rules["cross_border_score"]``) when ``metadata.country`` is present
      and is **not** a member of the configured home-country set. A missing/blank country is
      treated as *not* cross-border (fail-safe: absence of data never fabricates a signal).

    The three weights sum to at most 85 in the shipped config, but the result is defensively
    clamped to ``[0, 100]`` to honour the documented score range regardless of config edits.
    ``fraud_review`` is ``True`` only when ``risk_score >= rules["fraud_review_threshold"]``; fraud
    remains a *signal*, not a hard reject, for scores below that threshold.

    Returns ``{"risk_score": int, "fraud_review": bool, "signals": list[str]}``. Raises
    ``ValueError`` if ``amount`` or ``timestamp`` is missing/malformed, so callers fail closed
    (hold/raise) instead of silently scoring a bad record as low-risk.
    """
    signals: list[str] = []
    score = 0

    # Signal 1: high value -- currency-local comparison, no FX conversion (documented assumption).
    amount = protocol.to_decimal(data.get("amount"))
    if amount >= rules["high_value_threshold"]:
        score += rules["high_value_score"]
        signals.append(SIGNAL_HIGH_VALUE)

    # Signal 2: off-hours timing (UTC hour window, half-open [start, end)).
    ts = protocol.parse_timestamp(data.get("timestamp"))
    if rules["off_hours_start_hour"] <= ts.hour < rules["off_hours_end_hour"]:
        score += rules["off_hours_score"]
        signals.append(SIGNAL_OFF_HOURS)

    # Signal 3: cross-border -- metadata.country outside the home-country set. Missing/blank
    # country is NOT treated as cross-border (defensive default; never fabricates a signal).
    metadata = data.get("metadata")
    country = metadata.get("country") if isinstance(metadata, dict) else None
    if country and str(country).strip().upper() not in rules["home_countries"]:
        score += rules["cross_border_score"]
        signals.append(SIGNAL_CROSS_BORDER)

    risk_score = max(0, min(100, score))
    fraud_review = risk_score >= rules["fraud_review_threshold"]

    return {"risk_score": risk_score, "fraud_review": fraud_review, "signals": signals}


def process_message(
    message: dict[str, Any], *, next_agent: str | None = "compliance_checker"
) -> dict[str, Any]:
    """Score a validated transaction message for fraud risk.

    Reads a validated message (``data.status == "validated"``) handed off by the transaction
    validator, computes ``risk_score``/``fraud_review``/``fraud_signals`` via the pure
    :func:`score_transaction`, stamps ``data.status = "scored"``, and forwards the message onward to
    ``next_agent`` via ``shared/output/`` -- ``next_agent`` defaults to ``"compliance_checker"``
    (today's fixed pipeline order) but a caller driving a configurable stage order (see
    ``agents.rule_engine.determine_pipeline_order``) may pass a different agent name, or ``None`` if
    this detector is the *last* stage in the resolved order, in which case the message is written
    directly to ``shared/results/`` instead (terminal). Fraud is a signal, not a hard reject: every
    transaction that reaches this point is forwarded onward (or finalized) regardless of score.

    Idempotent: if a terminal result already exists for the transaction's id in
    ``shared/results/``, the stored outcome is returned unchanged and a single
    ``duplicate_ignored`` audit entry is logged -- the message is never re-scored or double-written.

    Fail-closed: in a non-default pipeline order this detector may run *before*
    ``transaction_validator`` and therefore see an unvalidated ``amount``/``timestamp`` that
    :func:`score_transaction` cannot parse. Rather than raise and crash the batch, any such scoring
    exception is caught here (only the exception's *class name* is audit-logged, never raw
    transaction data) and the message is written as a terminal ``status="error"``,
    ``reason=["fraud_scoring_error"]`` result -- never a silent low-risk score.
    """
    if not isinstance(message, dict):
        raise TypeError("message must be a dict")

    data = message.get("data")
    if not isinstance(data, dict):
        data = {}
        message["data"] = data

    transaction_id = protocol.transaction_id_of(message)

    # Idempotency check FIRST -- never recompute/re-score/double-write.
    if transaction_id and protocol.result_exists(transaction_id):
        protocol.audit_log(AGENT_NAME, transaction_id, "duplicate_ignored")
        stored = protocol.read_result(transaction_id)
        return stored if stored is not None else message

    log_id = transaction_id or str(message.get("message_id") or "")

    audit_extra = {
        "source_account": data.get("source_account"),
        "destination_account": data.get("destination_account"),
    }

    try:
        outcome = score_transaction(data, RULES)
    except Exception as exc:  # noqa: BLE001 -- fail-closed catch-all, never re-raise
        data["status"] = "error"
        data["decision"] = "error"
        data["reason"] = ["fraud_scoring_error"]
        message["source_agent"] = AGENT_NAME
        message["target_agent"] = AGENT_NAME
        protocol.write_result(message)
        protocol.audit_log(
            AGENT_NAME, log_id, "error", extra={"exception": type(exc).__name__}
        )
        return message

    data["risk_score"] = outcome["risk_score"]
    data["fraud_review"] = outcome["fraud_review"]
    data["fraud_signals"] = outcome["signals"]
    data["status"] = "scored"

    message["source_agent"] = AGENT_NAME

    if next_agent is None:
        # This detector is the last stage in the resolved pipeline order -- terminal write.
        message["target_agent"] = AGENT_NAME
        protocol.write_result(message)
    else:
        message["target_agent"] = next_agent
        protocol.write_message(message, "output")

    protocol.audit_log(
        AGENT_NAME,
        log_id,
        "scored",
        extra={
            **audit_extra,
            "risk_score": outcome["risk_score"],
            "fraud_review": outcome["fraud_review"],
        },
    )
    return message


# ---------------------------------------------------------------------------
# Queue-driven entrypoint (shared/output/[validated] -> shared/processing/ -> output/[scored])
# ---------------------------------------------------------------------------


def _process_queue() -> dict[str, int]:
    """Drain ``shared/output/`` for messages awaiting fraud scoring.

    Validated messages (``data.status == "validated"``) placed there by the transaction validator
    are moved to ``shared/processing/`` while being scored, then ``process_message`` re-writes the
    scored message back to ``shared/output/`` for the compliance checker to consume. Messages
    already at a later stage (e.g. ``status == "scored"``, awaiting compliance) are left untouched
    so this drain never reprocesses another agent's work. Malformed JSON files are skipped with a
    logged audit entry rather than aborting the whole batch.
    """
    protocol.ensure_dirs()
    processed = 0
    for path in protocol.list_messages("output"):
        try:
            message = protocol.read_message(path)
        except ValueError:
            protocol.audit_log(
                AGENT_NAME, path.stem, "rejected", extra={"reason": "malformed_input"}
            )
            try:
                path.unlink()
            except OSError:
                pass
            continue

        data = message.get("data") or {}
        if data.get("status") != "validated":
            continue  # not this agent's turn -- e.g. already scored, awaiting compliance

        try:
            moved_path = protocol.move_message(path, "processing")
            message = protocol.read_message(moved_path)
        except ValueError:
            protocol.audit_log(
                AGENT_NAME, path.stem, "rejected", extra={"reason": "malformed_input"}
            )
            continue

        process_message(message)
        try:
            moved_path.unlink()
        except OSError:
            pass
        processed += 1
    return {"processed": processed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fraud_detector", description="Banking pipeline fraud detector agent."
    )
    parser.parse_args(argv)

    result = _process_queue()
    print(f"Scored {result['processed']} message(s) from shared/output/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
