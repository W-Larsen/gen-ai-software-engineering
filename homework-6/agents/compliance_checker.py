"""Compliance Checker agent for the banking transaction-processing pipeline (serves M3).

Implements ``process_message(message: dict) -> dict`` per ``specification.md`` (Task: Compliance
Checker) -- the required **third** cooperating agent and the pipeline's final decision stage. It
reads a *scored* message handed off by ``agents.fraud_detector`` (``data.status == "scored"``),
applies three documented rules, and writes the terminal outcome to ``shared/results/``:

1. **Reporting threshold** -- ``requires_report = True`` when the canonical ``amount`` is
   ``>= rules["high_value_threshold"]`` in the transaction's stated currency (reason
   ``"regulatory_reporting_threshold"``). No live FX conversion -- same documented assumption as
   the fraud detector.
2. **Blocked / sanctioned accounts** -- reject (reason ``"blocked_account"``) if ``source_account``
   or ``destination_account`` appears in the configured ``agents/config/blocked_accounts.json``
   list (a synthetic fixture that intentionally never overlaps ``sample-transactions.json``).
3. **Regulated-transfer fields** -- reject (reason ``"missing_regulated_field:<field>"``) when the
   transaction is cross-border (``metadata.country`` outside the configured home-country set) or
   ``transaction_type == "wire_transfer"`` and ``metadata.channel`` or ``description`` is blank.

The final decision is always exactly one of ``{"cleared", "flagged", "rejected"}``:

* ``rejected``  -- rule 2 (blocked account) or rule 3 (missing regulated field) triggers.
* ``flagged``   -- otherwise, when ``fraud_review`` is ``True`` OR ``requires_report`` is ``True``.
* ``cleared``   -- otherwise.

This module reuses ``agents.protocol`` for the message envelope, atomic file I/O, Decimal parsing,
idempotency checks, and PII-masked audit logging -- it does not reimplement any of that. The
reporting threshold and home-country set are sourced from ``agents/config/fraud_rules.json`` (the
same versioned config the fraud detector uses) so the two agents never drift; the blocked-account
list is sourced from ``agents/config/blocked_accounts.json``. Neither is hardcoded inline.

**Fail-closed**: any screening exception is caught, the exception *class name only* (never raw
account data) is audit-logged, and the message is written with ``decision="flagged"`` and
``reason=["compliance_screening_error"]`` -- the checker never silently ``cleared``s an ambiguous
or erroring transaction.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from decimal import Decimal
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agents import protocol

AGENT_NAME = "compliance_checker"

_FRAUD_RULES_PATH = protocol.get_repo_root() / "agents" / "config" / "fraud_rules.json"
_BLOCKED_ACCOUNTS_PATH = protocol.get_repo_root() / "agents" / "config" / "blocked_accounts.json"

# Reason strings emitted by the three rules, plus the fail-closed sentinels. Named constants, not
# inline magic literals scattered through the rule logic.
REASON_REPORTING_THRESHOLD = "regulatory_reporting_threshold"
REASON_BLOCKED_ACCOUNT = "blocked_account"
REASON_MISSING_FIELD_PREFIX = "missing_regulated_field:"
REASON_FRAUD_REVIEW_FLAG = "fraud_review_flag"
REASON_SCREENING_ERROR = "compliance_screening_error"

DECISION_CLEARED = "cleared"
DECISION_FLAGGED = "flagged"
DECISION_REJECTED = "rejected"
VALID_DECISIONS = frozenset({DECISION_CLEARED, DECISION_FLAGGED, DECISION_REJECTED})


def load_rules(path: pathlib.Path | str | None = None) -> dict[str, Any]:
    """Load the reporting threshold + home-country set from ``agents/config/fraud_rules.json``.

    Reusing the *same* config file the fraud detector reads keeps the two agents' notion of
    "high value" and "home country" from drifting apart (per the spec's "Configuration over
    hardcoding" note). The threshold is parsed via ``protocol.to_decimal`` so every comparison
    stays ``Decimal``-only -- never ``float``.
    """
    cfg_path = pathlib.Path(path) if path else _FRAUD_RULES_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {
        "high_value_threshold": protocol.to_decimal(raw["high_value_threshold"]),
        "home_countries": frozenset(str(c).strip().upper() for c in raw["home_countries"]),
    }


def load_blocked_accounts(path: pathlib.Path | str | None = None) -> frozenset[str]:
    """Load the synthetic blocked/sanctioned-account list from ``agents/config/blocked_accounts.json``.

    This is a configurable, versioned fixture (never inline literals in the rule logic) that is
    guaranteed by the spec to never overlap any account number in ``sample-transactions.json``, so
    sample-data behaviour stays independent of the blocklist's specific contents.
    """
    cfg_path = pathlib.Path(path) if path else _BLOCKED_ACCOUNTS_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return frozenset(str(a).strip() for a in raw.get("blocked_accounts", []))


# Loaded once at import time; both loaders remain available for tests that want to exercise an
# alternate/synthetic config file (e.g. a blocked-account fixture or a different home-country set).
RULES: dict[str, Any] = load_rules()
BLOCKED_ACCOUNTS: frozenset[str] = load_blocked_accounts()


def _is_blank(value: Any) -> bool:
    """True if ``value`` is missing/None/an empty (or whitespace-only) string."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def screen_transaction(
    data: dict[str, Any],
    rules: dict[str, Any],
    blocked_accounts: frozenset[str],
) -> dict[str, Any]:
    """Pure, deterministic compliance-screening function -- **no file I/O, no logging**.

    Applies the three documented rules against ``data`` (a *scored* transaction payload carrying
    ``amount``, ``currency``, ``source_account``, ``destination_account``, ``transaction_type``,
    ``description``, ``metadata`` and the fraud detector's ``fraud_review``) and computes the final
    decision.

    Returns ``{"decision": str, "reason": list[str], "requires_report": bool}``. Raises
    ``ValueError`` if ``amount`` is malformed or ``fraud_review`` is missing/not a bool, so callers
    fail closed (flag, never silently clear) instead of screening an ambiguous record as low-risk.
    """
    reasons: list[str] = []

    # Rule 1: regulatory reporting threshold -- currency-local comparison, no FX conversion
    # (documented assumption, same as the fraud detector).
    amount = protocol.to_decimal(data.get("amount"))
    requires_report = amount >= rules["high_value_threshold"]
    if requires_report:
        reasons.append(REASON_REPORTING_THRESHOLD)

    # Rule 2: blocked / sanctioned account screening (exact match against the configured list).
    source_account = data.get("source_account")
    destination_account = data.get("destination_account")
    blocked_hit = (
        str(source_account).strip() in blocked_accounts
        or str(destination_account).strip() in blocked_accounts
    )
    if blocked_hit:
        reasons.append(REASON_BLOCKED_ACCOUNT)

    # Rule 3: regulated-transfer required fields for cross-border / wire transfers.
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    country = metadata.get("country")
    cross_border = bool(country) and str(country).strip().upper() not in rules["home_countries"]
    transaction_type = str(data.get("transaction_type", "")).strip().lower()
    is_wire_transfer = transaction_type == "wire_transfer"

    missing_field_reason: str | None = None
    if cross_border or is_wire_transfer:
        if _is_blank(metadata.get("channel")):
            missing_field_reason = f"{REASON_MISSING_FIELD_PREFIX}channel"
        elif _is_blank(data.get("description")):
            missing_field_reason = f"{REASON_MISSING_FIELD_PREFIX}description"
    if missing_field_reason:
        reasons.append(missing_field_reason)

    # fraud_review must be an explicit bool carried forward from the fraud detector; a missing or
    # malformed value is ambiguous input and must fail closed (raised here, caught by the caller).
    fraud_review = data.get("fraud_review")
    if not isinstance(fraud_review, bool):
        raise ValueError("missing_or_invalid_fraud_review")

    # Final decision: rejected takes precedence over flagged/cleared (rules 2/3 are hard stops).
    if blocked_hit or missing_field_reason:
        decision = DECISION_REJECTED
    elif fraud_review or requires_report:
        decision = DECISION_FLAGGED
        if not reasons:
            # Keep the reason list non-empty for an auditable flagged decision driven purely by
            # the fraud detector's signal (requires_report already contributes its own reason).
            reasons.append(REASON_FRAUD_REVIEW_FLAG)
    else:
        decision = DECISION_CLEARED
        reasons = []  # spec: reason list is empty exactly when decision == "cleared".

    return {"decision": decision, "reason": reasons, "requires_report": requires_report}


def process_message(message: dict[str, Any]) -> dict[str, Any]:
    """Apply compliance screening to a scored transaction message and write the final outcome.

    Reads a scored message (``data.status == "scored"``) handed off by the fraud detector, applies
    :func:`screen_transaction`, stamps ``data.status`` to the resulting ``decision``, and writes the
    terminal message to ``shared/results/`` via ``protocol.write_result`` (atomic, keyed by
    ``transaction_id``). ``decision`` is always a member of the closed set ``{cleared, flagged,
    rejected}`` -- never any other string.

    Idempotent: if a terminal result already exists for the transaction's id, the stored outcome is
    returned unchanged and a single ``duplicate_ignored`` audit entry is logged -- the message is
    never re-screened or double-written.

    Fail-closed: any exception raised while screening (malformed amount, missing ``fraud_review``,
    unreadable config, etc.) is caught here; only the exception's *class name* is audit-logged
    (never raw account data), and the message is written with ``decision="flagged"``,
    ``reason=["compliance_screening_error"]`` -- an ambiguous/erroring transaction is never
    silently cleared.
    """
    if not isinstance(message, dict):
        raise TypeError("message must be a dict")

    data = message.get("data")
    if not isinstance(data, dict):
        data = {}
        message["data"] = data

    transaction_id = protocol.transaction_id_of(message)

    # Idempotency check FIRST -- never recompute/re-screen/double-write.
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
        outcome = screen_transaction(data, RULES, BLOCKED_ACCOUNTS)
        decision = outcome["decision"]
        reasons = outcome["reason"]
        requires_report = outcome["requires_report"]
        if decision not in VALID_DECISIONS:  # defensive -- should be unreachable
            raise ValueError(f"invalid_decision:{decision}")
    except Exception as exc:  # noqa: BLE001 -- fail-closed catch-all, never re-raise
        decision = DECISION_FLAGGED
        reasons = [REASON_SCREENING_ERROR]
        requires_report = bool(data.get("requires_report", False))
        protocol.audit_log(
            AGENT_NAME,
            log_id,
            decision,
            extra={"reason": reasons, "exception": type(exc).__name__},
        )
        data["decision"] = decision
        data["reason"] = reasons
        data["requires_report"] = requires_report
        data["status"] = decision
        message["source_agent"] = AGENT_NAME
        message["target_agent"] = "integrator"
        protocol.write_result(message)
        return message

    data["decision"] = decision
    data["reason"] = reasons
    data["requires_report"] = requires_report
    data["status"] = decision
    # risk_score / fraud_review are already present on data (carried forward from the fraud
    # detector) and are left untouched, per the spec's "Keep data.risk_score and data.fraud_review
    # present" requirement.

    message["source_agent"] = AGENT_NAME
    message["target_agent"] = "integrator"
    protocol.write_result(message)

    protocol.audit_log(
        AGENT_NAME,
        log_id,
        decision,
        extra={
            **audit_extra,
            "reason": reasons,
            "requires_report": requires_report,
        },
    )
    return message


# ---------------------------------------------------------------------------
# Queue-driven entrypoint (shared/output/[scored] -> shared/processing/ -> shared/results/)
# ---------------------------------------------------------------------------


def _process_queue() -> dict[str, int]:
    """Drain ``shared/output/`` for scored messages awaiting a compliance decision.

    Scored messages (``data.status == "scored"``) placed there by the fraud detector are moved to
    ``shared/processing/`` while being screened, then ``process_message`` writes the terminal
    outcome to ``shared/results/``. Messages not yet at the ``scored`` stage are left untouched so
    this drain never reprocesses another agent's in-flight work. Malformed JSON files are skipped
    with a logged audit entry rather than aborting the whole batch.
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
        if data.get("status") != "scored":
            continue  # not this agent's turn yet

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
        prog="compliance_checker", description="Banking pipeline compliance checker agent."
    )
    parser.parse_args(argv)

    result = _process_queue()
    print(f"Screened {result['processed']} message(s) from shared/output/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
