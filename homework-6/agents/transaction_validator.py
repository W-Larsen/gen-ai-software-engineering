"""Transaction Validator agent for the banking transaction-processing pipeline (serves M1).

Implements ``process_message(message: dict) -> dict`` per ``specification.md`` (Task: Transaction
Validator) and ``TASKS.md`` (Task 2). The validator is the first stage of the pipeline: it checks
required fields, parses the amount as ``decimal.Decimal`` (never ``float``), validates the currency
against ISO 4217, and applies the negative-amount/refund rule. Successful messages are handed off
to the fraud detector via ``shared/output/``; rejected messages are terminal and are written
directly to ``shared/results/`` with a populated ``reason``, bypassing fraud/compliance entirely.

This module reuses ``agents.protocol`` for the message envelope, atomic file I/O, Decimal/ISO 4217
handling, idempotency checks, and PII-masked audit logging -- it does not reimplement any of that.
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

AGENT_NAME = "transaction_validator"

# Order matters: this is also the order in which checks are applied.
REQUIRED_FIELDS: tuple[str, ...] = (
    "transaction_id",
    "amount",
    "currency",
    "source_account",
    "destination_account",
    "timestamp",
)


def _is_blank(value: Any) -> bool:
    """True if ``value`` is missing/None/an empty (or whitespace-only) string."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _first_missing_field(data: dict[str, Any]) -> str | None:
    """Return the name of the first required field that is absent or blank, else ``None``."""
    for field in REQUIRED_FIELDS:
        if field not in data or _is_blank(data.get(field)):
            return field
    return None


def _validate_core(
    data: dict[str, Any],
) -> tuple[bool, str | None, Decimal | None, str | None]:
    """Pure validation logic (no I/O, no logging) so it is independently testable and reusable by
    both ``process_message`` and ``--dry-run``.

    Checks are applied strictly in this order: required-field presence; decimal-parseable amount;
    ISO 4217 currency membership; negative-amount-vs-refund rule.

    Returns ``(is_valid, reason, canonical_amount, direction)``. ``reason`` is populated only when
    ``is_valid`` is False. ``canonical_amount``/``direction`` are populated only when valid.
    """
    # 1. Required-field presence.
    missing = _first_missing_field(data)
    if missing:
        return False, f"missing_required_field:{missing}", None, None

    # 2. Decimal-parseable amount (never float).
    raw_amount = data.get("amount")
    try:
        decimal_amount = protocol.to_decimal(raw_amount)
    except ValueError as exc:
        return False, str(exc), None, None

    # 3. ISO 4217 currency membership.
    currency = data.get("currency")
    if not protocol.is_valid_currency(currency):
        return False, f"invalid_currency_code:{currency}", None, None

    canonical = protocol.quantize_amount(decimal_amount, currency)

    # 4. Negative-amount-vs-refund rule.
    direction: str | None = None
    if canonical < 0:
        transaction_type = str(data.get("transaction_type", "")).strip().lower()
        if transaction_type == "refund":
            canonical = abs(canonical)
            direction = "refund_credit"
        else:
            return False, "negative_amount_not_permitted", None, None

    return True, None, canonical, direction


def process_message(
    message: dict[str, Any], *, next_agent: str | None = "fraud_detector"
) -> dict[str, Any]:
    """Validate an incoming transaction message.

    On success the message is routed onward to ``next_agent`` via ``shared/output/`` with
    ``data.status = "validated"`` -- ``next_agent`` defaults to ``"fraud_detector"`` (today's fixed
    pipeline order) but a caller driving a configurable stage order (see
    ``agents.rule_engine.determine_pipeline_order``) may pass a different agent name, or ``None`` if
    this validator is the *last* stage in the resolved order, in which case the message is written
    directly to ``shared/results/`` instead (terminal). On failure the message is always written
    directly to ``shared/results/`` with ``data.status = "rejected"`` and a populated
    ``data.reason``, bypassing fraud/compliance regardless of ``next_agent``.

    Idempotent: if a result already exists for the transaction's id, the stored outcome is
    returned unchanged and a single ``duplicate_ignored`` audit entry is logged -- the message is
    never reprocessed or double-written. Never mutates the incoming message's ``transaction_id``.
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

    # A missing/blank transaction_id must not crash the agent; fall back to the message_id for
    # audit logging and result filing (handled transparently by protocol.write_result), and let the
    # required-field check below surface the proper rejection reason.
    log_id = transaction_id or str(message.get("message_id") or "")

    is_valid, reason, canonical, direction = _validate_core(data)

    audit_extra = {
        "source_account": data.get("source_account"),
        "destination_account": data.get("destination_account"),
    }

    if not is_valid:
        data["status"] = "rejected"
        data["reason"] = reason
        message["source_agent"] = AGENT_NAME
        message["target_agent"] = "integrator"
        protocol.write_result(message)
        protocol.audit_log(
            AGENT_NAME, log_id, "rejected", extra={**audit_extra, "reason": reason}
        )
        return message

    data["amount"] = protocol.format_amount(canonical)
    data["status"] = "validated"
    if direction:
        data["direction"] = direction
    message["source_agent"] = AGENT_NAME

    if next_agent is None:
        # This validator is the last stage in the resolved pipeline order -- terminal write.
        message["target_agent"] = AGENT_NAME
        protocol.write_result(message)
    else:
        message["target_agent"] = next_agent
        protocol.write_message(message, "output")

    protocol.audit_log(AGENT_NAME, log_id, "validated", extra=audit_extra)
    return message


# ---------------------------------------------------------------------------
# Queue-driven entrypoint (shared/input/ -> shared/processing/ -> output/results)
# ---------------------------------------------------------------------------


def _process_queue() -> dict[str, int]:
    """Drain ``shared/input/``: move each message to ``shared/processing/`` while working, run
    ``process_message`` (which writes the terminal/handoff message itself), then clear the
    processing copy. Malformed JSON files are skipped with a rejected+``malformed_input`` audit
    entry rather than aborting the whole batch.
    """
    protocol.ensure_dirs()
    processed = 0
    for path in protocol.list_messages("input"):
        try:
            moved_path = protocol.move_message(path, "processing")
            message = protocol.read_message(moved_path)
        except ValueError:
            protocol.audit_log(
                AGENT_NAME, path.stem, "rejected", extra={"reason": "malformed_input"}
            )
            try:
                path.unlink()
            except OSError:
                pass
            continue

        process_message(message)
        try:
            moved_path.unlink()
        except OSError:
            pass
        processed += 1
    return {"processed": processed}


# ---------------------------------------------------------------------------
# --dry-run CLI
# ---------------------------------------------------------------------------


def _run_dry_run(sample_file: str | None = None) -> dict[str, Any]:
    """Validate every record in ``sample_file`` (default ``sample-transactions.json``) using the
    pure validation core only -- no filesystem writes under ``shared/`` are ever performed.
    """
    root = protocol.get_repo_root()
    path = pathlib.Path(sample_file).resolve() if sample_file else root / "sample-transactions.json"

    with open(path, "r", encoding="utf-8") as fh:
        records = json.load(fh)

    total = len(records)
    valid = 0
    rejections: list[tuple[str, str]] = []

    for record in records:
        if not isinstance(record, dict):
            rejections.append((str(record), "malformed_input"))
            continue
        ok, reason, _canonical, _direction = _validate_core(record)
        if ok:
            valid += 1
        else:
            txn_id = str(record.get("transaction_id", "<unknown>"))
            rejections.append((txn_id, reason or "unknown"))

    invalid = total - valid

    print(f"Total: {total}")
    print(f"Valid: {valid}")
    print(f"Invalid: {invalid}")
    if rejections:
        print("Rejection reasons:")
        for txn_id, reason in rejections:
            print(f"  {txn_id}: {reason}")

    return {"total": total, "valid": valid, "invalid": invalid, "rejections": rejections}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="transaction_validator", description="Banking pipeline transaction validator agent."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate sample-transactions.json without moving/writing any shared/ files.",
    )
    parser.add_argument(
        "--sample-file",
        default=None,
        help="Override the sample data file used by --dry-run (defaults to sample-transactions.json).",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        _run_dry_run(args.sample_file)
        return 0

    result = _process_queue()
    print(f"Processed {result['processed']} message(s) from shared/input/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
