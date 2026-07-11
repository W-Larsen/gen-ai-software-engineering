"""Unit tests for agents/compliance_checker.py (serves M3).

Covers, per specification.md's "Compliance Checker" Low-Level Task and Verification & Test
Strategy section:

* the reporting-threshold rule (>= $10,000 => requires_report=true, including the TXN003
  $9,999.99 boundary),
* a synthetic blocked-account fixture (using ACC-BLOCK-0001, which never overlaps sample data)
  rejected with reason 'blocked_account',
* a synthetic missing-regulated-field fixture rejected with reason starting with
  'missing_regulated_field',
* a fail-closed screening-error path (decision='flagged', reason=['compliance_screening_error']),
* a full TXN001-TXN008 reconciliation: every produced result has decision in
  {cleared, flagged, rejected}, with the specific TXN002/TXN003/TXN005 outcomes called out.

The filesystem is isolated per test via PIPELINE_SHARED_ROOT / PIPELINE_LOGS_DIR env vars pointing
at pytest's tmp_path, so no test ever touches the project's real shared/ or logs/ tree.
"""

from __future__ import annotations

import copy
import json
import runpy
import sys as _sys
from pathlib import Path

import pytest

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import protocol
from agents import compliance_checker
from agents import fraud_detector

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


def _scored_data(transaction_id: str) -> dict:
    """Build a scored payload for a sample transaction as the fraud detector would hand it off."""
    data = _sample(transaction_id)
    data["status"] = "validated"
    outcome = fraud_detector.score_transaction(data, fraud_detector.RULES)
    data["risk_score"] = outcome["risk_score"]
    data["fraud_review"] = outcome["fraud_review"]
    data["fraud_signals"] = outcome["signals"]
    data["status"] = "scored"
    return data


def _incoming_message(data: dict) -> dict:
    return protocol.build_message(
        data, source_agent="fraud_detector", target_agent="compliance_checker"
    )


# ---------------------------------------------------------------------------
# Rule 1: regulatory reporting threshold (including the TXN003 boundary)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "amount, expected_requires_report",
    [
        ("10000.00", True),   # exactly at the threshold -- strict >= triggers
        ("10000.01", True),
        ("9999.99", False),   # TXN003 boundary -- must NOT trigger
        ("500.00", False),
    ],
)
def test_reporting_threshold_boundary(amount, expected_requires_report):
    data = _scored_data("TXN001")
    data["amount"] = amount
    outcome = compliance_checker.screen_transaction(
        data, compliance_checker.RULES, compliance_checker.BLOCKED_ACCOUNTS
    )
    assert outcome["requires_report"] is expected_requires_report
    if expected_requires_report:
        assert compliance_checker.REASON_REPORTING_THRESHOLD in outcome["reason"]
    else:
        assert compliance_checker.REASON_REPORTING_THRESHOLD not in outcome["reason"]


def test_txn003_requires_report_false_end_to_end():
    result = compliance_checker.process_message(_incoming_message(_scored_data("TXN003")))
    assert result["data"]["requires_report"] is False


# ---------------------------------------------------------------------------
# Rule 2: blocked / sanctioned account screening (synthetic fixture only)
# ---------------------------------------------------------------------------


def test_blocked_source_account_is_rejected():
    data = _scored_data("TXN001")
    data["source_account"] = "ACC-BLOCK-0001"  # synthetic fixture, never in sample data
    assert "ACC-BLOCK-0001" not in {r["source_account"] for r in _sample_records()}

    result = compliance_checker.process_message(_incoming_message(data))

    assert result["data"]["decision"] == "rejected"
    assert "blocked_account" in result["data"]["reason"]


def test_blocked_destination_account_is_rejected():
    data = _scored_data("TXN008")
    data["destination_account"] = "ACC-SANCTION-9"

    result = compliance_checker.process_message(_incoming_message(data))

    assert result["data"]["decision"] == "rejected"
    assert "blocked_account" in result["data"]["reason"]


def test_blocked_accounts_config_does_not_overlap_sample_data():
    sample_accounts = set()
    for record in _sample_records():
        sample_accounts.add(record["source_account"])
        sample_accounts.add(record["destination_account"])
    assert sample_accounts.isdisjoint(compliance_checker.BLOCKED_ACCOUNTS)


# ---------------------------------------------------------------------------
# Rule 3: missing regulated field on a cross-border / wire-transfer transaction
# ---------------------------------------------------------------------------


def test_missing_channel_on_wire_transfer_is_rejected():
    data = _scored_data("TXN002")  # wire_transfer, US -> US
    data["metadata"]["channel"] = ""  # blank channel

    result = compliance_checker.process_message(_incoming_message(data))

    assert result["data"]["decision"] == "rejected"
    assert any(r.startswith("missing_regulated_field") for r in result["data"]["reason"])
    assert "missing_regulated_field:channel" in result["data"]["reason"]


def test_missing_description_on_cross_border_is_rejected():
    data = _scored_data("TXN004")  # cross-border (DE)
    data["description"] = ""

    result = compliance_checker.process_message(_incoming_message(data))

    assert result["data"]["decision"] == "rejected"
    assert "missing_regulated_field:description" in result["data"]["reason"]


def test_missing_field_not_triggered_for_domestic_non_wire_transfer():
    data = _scored_data("TXN001")  # transfer, US -> US, not cross-border
    data["metadata"]["channel"] = ""  # blank, but rule 3 shouldn't even apply
    data["description"] = ""

    outcome = compliance_checker.screen_transaction(
        data, compliance_checker.RULES, compliance_checker.BLOCKED_ACCOUNTS
    )
    assert not any(r.startswith("missing_regulated_field") for r in outcome["reason"])


# ---------------------------------------------------------------------------
# Fail-closed: screening exceptions never resolve to a silent 'cleared'
# ---------------------------------------------------------------------------


def test_missing_fraud_review_fails_closed_to_flagged():
    data = _scored_data("TXN001")
    del data["fraud_review"]  # ambiguous input -- must not be silently cleared

    result = compliance_checker.process_message(_incoming_message(data))

    assert result["data"]["decision"] == "flagged"
    assert result["data"]["reason"] == ["compliance_screening_error"]


def test_malformed_amount_fails_closed_to_flagged():
    data = _scored_data("TXN001")
    data["amount"] = "not-a-number"

    result = compliance_checker.process_message(_incoming_message(data))

    assert result["data"]["decision"] == "flagged"
    assert result["data"]["reason"] == ["compliance_screening_error"]


def test_decision_is_always_in_closed_set():
    assert compliance_checker.VALID_DECISIONS == {"cleared", "flagged", "rejected"}


# ---------------------------------------------------------------------------
# TXN001-TXN008 reconciliation (TXN006 never reaches compliance -- validator-rejected upstream)
# ---------------------------------------------------------------------------

EXPECTED_DECISIONS = {
    # txn_id: (decision, requires_report)
    "TXN001": ("cleared", False),
    "TXN002": ("flagged", True),
    "TXN003": ("cleared", False),
    "TXN004": ("cleared", False),
    "TXN005": ("flagged", True),
    "TXN007": ("cleared", False),
    "TXN008": ("cleared", False),
}


@pytest.mark.parametrize("txn_id", sorted(EXPECTED_DECISIONS))
def test_sample_transaction_outcomes(txn_id):
    expected_decision, expected_requires_report = EXPECTED_DECISIONS[txn_id]

    result = compliance_checker.process_message(_incoming_message(_scored_data(txn_id)))

    assert result["data"]["decision"] == expected_decision
    assert result["data"]["requires_report"] is expected_requires_report
    assert result["data"]["status"] == expected_decision
    assert result["data"]["decision"] in {"cleared", "flagged", "rejected"}
    # risk_score / fraud_review carried forward from the fraud detector, per spec.
    assert "risk_score" in result["data"]
    assert "fraud_review" in result["data"]


def test_txn002_and_txn005_flagged_with_requires_report_true():
    for txn_id in ("TXN002", "TXN005"):
        result = compliance_checker.process_message(_incoming_message(_scored_data(txn_id)))
        assert result["data"]["decision"] == "flagged"
        assert result["data"]["requires_report"] is True


def test_result_written_to_shared_results():
    compliance_checker.process_message(_incoming_message(_scored_data("TXN001")))
    assert (protocol.shared_subdir("results") / "TXN001.json").exists()


def test_full_sample_run_reconciliation_all_decisions_in_closed_set():
    """Reconciliation check: every produced result has decision in {cleared, flagged, rejected}."""
    for txn_id in EXPECTED_DECISIONS:
        compliance_checker.process_message(_incoming_message(_scored_data(txn_id)))

    for path in protocol.list_messages("results"):
        message = protocol.read_message(path)
        assert message["data"]["decision"] in {"cleared", "flagged", "rejected"}


# ---------------------------------------------------------------------------
# Idempotency: existing shared/results/ entry short-circuits re-screening
# ---------------------------------------------------------------------------


def test_duplicate_transaction_with_existing_result_is_idempotent(monkeypatch):
    data = _scored_data("TXN002")
    message = _incoming_message(data)
    txn_id = protocol.transaction_id_of(message)

    first = compliance_checker.process_message(message)
    assert first["data"]["decision"] == "flagged"

    write_calls: list[dict] = []
    original_write_result = protocol.write_result

    def _tracked_write_result(msg):
        write_calls.append(msg)
        return original_write_result(msg)

    monkeypatch.setattr(protocol, "write_result", _tracked_write_result)

    second = compliance_checker.process_message(_incoming_message(_scored_data("TXN002")))

    assert second["data"]["decision"] == "flagged"
    assert write_calls == []  # never re-screened/re-written


# ---------------------------------------------------------------------------
# _is_blank: non-string, non-None value is never blank
# ---------------------------------------------------------------------------


def test_is_blank_non_string_value_is_not_blank():
    assert compliance_checker._is_blank(0) is False
    assert compliance_checker._is_blank(123) is False
    assert compliance_checker._is_blank([]) is False


def test_is_blank_none_is_blank():
    assert compliance_checker._is_blank(None) is True


# ---------------------------------------------------------------------------
# fraud_review_flag reason: decision flagged purely on fraud_review, with no other reason
# ---------------------------------------------------------------------------


def test_flagged_reason_defaults_to_fraud_review_flag_when_no_other_reason():
    data = _scored_data("TXN001")  # amount well below the reporting threshold
    data["fraud_review"] = True  # force a flag with no accompanying reporting/blocked reason

    outcome = compliance_checker.screen_transaction(
        data, compliance_checker.RULES, compliance_checker.BLOCKED_ACCOUNTS
    )

    assert outcome["decision"] == "flagged"
    assert outcome["reason"] == [compliance_checker.REASON_FRAUD_REVIEW_FLAG]


# ---------------------------------------------------------------------------
# process_message: type/coercion defensiveness
# ---------------------------------------------------------------------------


def test_process_message_non_dict_message_raises_type_error():
    with pytest.raises(TypeError):
        compliance_checker.process_message("not-a-message")


def test_process_message_non_dict_data_is_coerced_to_empty_dict():
    message = protocol.build_message(
        {}, source_agent="fraud_detector", target_agent="compliance_checker"
    )
    message["data"] = "not-a-dict"

    result = compliance_checker.process_message(message)

    assert isinstance(message["data"], dict)
    # Coerced-to-empty data has no amount/fraud_review -- fails closed rather than crashing.
    assert result["data"]["decision"] == "flagged"
    assert result["data"]["reason"] == [compliance_checker.REASON_SCREENING_ERROR]


# ---------------------------------------------------------------------------
# Defensive: an out-of-band decision from screen_transaction is caught fail-closed
# ---------------------------------------------------------------------------


def test_defensive_invalid_decision_is_caught_fail_closed(monkeypatch):
    def _bogus_screen(data, rules, blocked_accounts):
        return {"decision": "not-a-real-decision", "reason": [], "requires_report": False}

    monkeypatch.setattr(compliance_checker, "screen_transaction", _bogus_screen)

    result = compliance_checker.process_message(
        _incoming_message(_scored_data("TXN001"))
    )

    assert result["data"]["decision"] == "flagged"
    assert result["data"]["reason"] == [compliance_checker.REASON_SCREENING_ERROR]


# ---------------------------------------------------------------------------
# _process_queue: drains shared/output/ for scored messages awaiting a compliance decision
# ---------------------------------------------------------------------------


def test_process_queue_screens_scored_message_and_writes_result():
    protocol.write_message(_incoming_message(_scored_data("TXN001")), "output")

    result = compliance_checker._process_queue()

    assert result["processed"] == 1
    assert list(protocol.shared_subdir("processing").glob("*.json")) == []
    final = protocol.read_result("TXN001")
    assert final["data"]["decision"] in {"cleared", "flagged", "rejected"}


def test_process_queue_skips_malformed_json_file_without_aborting_batch():
    output_dir = protocol.shared_subdir("output")
    bad_path = output_dir / "BAD001.json"
    bad_path.write_text("{not valid json", encoding="utf-8")

    protocol.write_message(_incoming_message(_scored_data("TXN001")), "output")

    result = compliance_checker._process_queue()

    assert result["processed"] == 1
    assert not bad_path.exists()


def test_process_queue_leaves_non_scored_message_untouched():
    data = _sample("TXN001")
    data["status"] = "validated"  # not yet scored -- not this agent's turn
    protocol.write_message(_incoming_message(data), "output")

    result = compliance_checker._process_queue()

    assert result["processed"] == 0
    still_there = protocol.read_message(protocol.shared_subdir("output") / "TXN001.json")
    assert still_there["data"]["status"] == "validated"


def test_process_queue_tolerates_unlink_failures_on_cleanup(monkeypatch):
    """Best-effort cleanup unlinks must never crash the batch (edge case: locked/removed file)."""
    output_dir = protocol.shared_subdir("output")
    bad_path = output_dir / "BAD002.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    protocol.write_message(_incoming_message(_scored_data("TXN001")), "output")

    def _raise_unlink(self, *args, **kwargs):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(Path, "unlink", _raise_unlink)

    result = compliance_checker._process_queue()

    assert result["processed"] == 1


def test_process_queue_skips_on_move_race_condition(monkeypatch):
    """Simulate the file disappearing/mutating between the initial read and the move-to-processing
    step (edge case: a concurrent writer corrupts the file mid-drain)."""
    protocol.write_message(_incoming_message(_scored_data("TXN001")), "output")

    def _raise(*_args, **_kwargs):
        raise ValueError("malformed_input: simulated race")

    monkeypatch.setattr(protocol, "move_message", _raise)

    result = compliance_checker._process_queue()

    assert result["processed"] == 0


# ---------------------------------------------------------------------------
# main(): CLI entrypoint, and the ``python -m`` / ``__main__`` guard
# ---------------------------------------------------------------------------


def test_main_drains_the_queue(capsys):
    protocol.write_message(_incoming_message(_scored_data("TXN001")), "output")

    exit_code = compliance_checker.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Screened 1 message(s) from shared/output/." in captured.out


def test_main_handles_empty_queue(capsys):
    exit_code = compliance_checker.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Screened 0 message(s) from shared/output/." in captured.out


def test_module_dunder_main_entrypoint(monkeypatch):
    """Exercise ``if __name__ == '__main__': raise SystemExit(main())`` directly."""
    monkeypatch.setattr(_sys, "argv", ["compliance_checker"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("agents.compliance_checker", run_name="__main__")

    assert exc_info.value.code == 0
