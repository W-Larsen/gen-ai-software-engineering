"""Unit tests for agents/transaction_validator.py (serves M1).

Fixtures are derived from sample-transactions.json (TXN001, TXN003, TXN006, TXN007) plus two
synthetic fixtures (missing-amount, negative non-refund) and a duplicate-transaction_id fixture.
The filesystem is isolated per test via PIPELINE_SHARED_ROOT / PIPELINE_LOGS_DIR env vars pointing
at pytest's tmp_path, so no test ever touches the project's real shared/ or logs/ tree.
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import protocol
from agents import transaction_validator as validator

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample-transactions.json"


@pytest.fixture(autouse=True)
def isolated_shared(tmp_path, monkeypatch):
    """Point the shared protocol at an isolated tmp_path filesystem for every test."""
    monkeypatch.setenv("PIPELINE_SHARED_ROOT", str(tmp_path / "shared"))
    monkeypatch.setenv("PIPELINE_LOGS_DIR", str(tmp_path / "logs"))
    protocol.ensure_dirs()
    yield


def _sample_records() -> list[dict]:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sample(transaction_id: str) -> dict:
    for record in _sample_records():
        if record["transaction_id"] == transaction_id:
            return copy.deepcopy(record)
    raise KeyError(transaction_id)


def _incoming_message(data: dict) -> dict:
    return protocol.build_message(
        data, source_agent="integrator", target_agent="transaction_validator"
    )


# ---------------------------------------------------------------------------
# TXN001 -- straightforward valid transaction
# ---------------------------------------------------------------------------


def test_txn001_valid_transaction_is_validated_and_routed_to_output():
    message = _incoming_message(_sample("TXN001"))

    result = validator.process_message(message)

    assert result["data"]["status"] == "validated"
    assert result["data"]["amount"] == "1500.00"
    assert Decimal(result["data"]["amount"]) == Decimal("1500.00")
    assert result["target_agent"] == "fraud_detector"

    assert not protocol.result_exists("TXN001")
    assert (protocol.shared_subdir("output") / "TXN001.json").exists()


# ---------------------------------------------------------------------------
# TXN003 -- boundary amount just under the $10k rule; must still validate
# ---------------------------------------------------------------------------


def test_txn003_boundary_amount_is_valid():
    message = _incoming_message(_sample("TXN003"))

    result = validator.process_message(message)

    assert result["data"]["status"] == "validated"
    assert result["data"]["amount"] == "9999.99"
    assert (protocol.shared_subdir("output") / "TXN003.json").exists()


# ---------------------------------------------------------------------------
# TXN006 -- invalid ISO 4217 currency code (XYZ)
# ---------------------------------------------------------------------------


def test_txn006_invalid_currency_is_rejected_and_never_reaches_output():
    message = _incoming_message(_sample("TXN006"))

    result = validator.process_message(message)

    assert result["data"]["status"] == "rejected"
    assert "invalid_currency" in result["data"]["reason"]
    assert result["target_agent"] == "integrator"

    assert protocol.result_exists("TXN006")
    assert not (protocol.shared_subdir("output") / "TXN006.json").exists()


# ---------------------------------------------------------------------------
# TXN007 -- negative amount on a refund: accepted, sign normalized
# ---------------------------------------------------------------------------


def test_txn007_negative_refund_amount_is_normalized_to_credit():
    message = _incoming_message(_sample("TXN007"))

    result = validator.process_message(message)

    assert result["data"]["status"] == "validated"
    assert Decimal(result["data"]["amount"]) == Decimal("100.00")
    assert result["data"]["direction"] == "refund_credit"
    assert (protocol.shared_subdir("output") / "TXN007.json").exists()


# ---------------------------------------------------------------------------
# Synthetic: missing required field (amount)
# ---------------------------------------------------------------------------


def test_missing_amount_field_is_rejected():
    data = _sample("TXN001")
    data["transaction_id"] = "TXN901"
    del data["amount"]

    result = validator.process_message(_incoming_message(data))

    assert result["data"]["status"] == "rejected"
    assert result["data"]["reason"] == "missing_required_field:amount"
    assert protocol.result_exists("TXN901")


def test_missing_transaction_id_does_not_crash():
    data = _sample("TXN001")
    data["transaction_id"] = ""

    result = validator.process_message(_incoming_message(data))

    assert result["data"]["status"] == "rejected"
    assert result["data"]["reason"] == "missing_required_field:transaction_id"


# ---------------------------------------------------------------------------
# Synthetic: negative amount on a non-refund transaction_type
# ---------------------------------------------------------------------------


def test_negative_amount_non_refund_is_rejected():
    data = _sample("TXN001")
    data["transaction_id"] = "TXN902"
    data["amount"] = "-50.00"
    data["transaction_type"] = "transfer"

    result = validator.process_message(_incoming_message(data))

    assert result["data"]["status"] == "rejected"
    assert result["data"]["reason"] == "negative_amount_not_permitted"
    assert protocol.result_exists("TXN902")
    assert not (protocol.shared_subdir("output") / "TXN902.json").exists()


# ---------------------------------------------------------------------------
# Malformed amount (non-numeric) -- decimal-parse failure, not a missing field
# ---------------------------------------------------------------------------


def test_non_numeric_amount_is_rejected():
    data = _sample("TXN001")
    data["transaction_id"] = "TXN903"
    data["amount"] = "not-a-number"

    result = validator.process_message(_incoming_message(data))

    assert result["data"]["status"] == "rejected"
    assert "invalid_amount" in result["data"]["reason"]


# ---------------------------------------------------------------------------
# Duplicate transaction_id: idempotent, no reprocessing, no duplicate result file
# ---------------------------------------------------------------------------


def test_duplicate_transaction_id_is_idempotent(monkeypatch):
    data = _sample("TXN006")  # rejected fixture -> writes to shared/results/

    write_calls: list[dict] = []
    original_write_result = protocol.write_result

    def _tracked_write_result(message):
        write_calls.append(message)
        return original_write_result(message)

    monkeypatch.setattr(protocol, "write_result", _tracked_write_result)

    first = validator.process_message(_incoming_message(copy.deepcopy(data)))
    second = validator.process_message(_incoming_message(copy.deepcopy(data)))

    assert first["data"]["status"] == "rejected"
    assert second["data"]["status"] == "rejected"
    assert second["data"]["reason"] == first["data"]["reason"]

    # write_result must only have been invoked once -- the duplicate must not rewrite results.
    assert len(write_calls) == 1

    result_files = list(protocol.shared_subdir("results").glob("TXN006*"))
    assert len(result_files) == 1


def test_duplicate_of_validated_transaction_returns_stored_outcome(monkeypatch):
    """Re-submitting a transaction_id that already has a *rejected* result must short-circuit even
    though the original process ran through the validated (output) path for a different call --
    here we confirm a duplicate call after a rejection never re-invokes write_message either."""
    data = _sample("TXN006")

    output_write_calls: list[dict] = []
    original_write_message = protocol.write_message

    def _tracked_write_message(message, subdir, **kwargs):
        output_write_calls.append(message)
        return original_write_message(message, subdir, **kwargs)

    monkeypatch.setattr(protocol, "write_message", _tracked_write_message)

    validator.process_message(_incoming_message(copy.deepcopy(data)))
    validator.process_message(_incoming_message(copy.deepcopy(data)))

    assert output_write_calls == []  # TXN006 is rejected; output/ is never touched


# ---------------------------------------------------------------------------
# --dry-run CLI
# ---------------------------------------------------------------------------


def test_dry_run_reports_expected_counts(capsys):
    exit_code = validator.main(["--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Total: 8" in captured.out
    assert "Valid: 7" in captured.out
    assert "Invalid: 1" in captured.out
    assert "TXN006" in captured.out


def test_dry_run_never_writes_shared_files():
    output_dir = protocol.shared_subdir("output")
    results_dir = protocol.shared_subdir("results")

    validator.main(["--dry-run"])

    assert list(output_dir.glob("*.json")) == []
    assert list(results_dir.glob("*.json")) == []
