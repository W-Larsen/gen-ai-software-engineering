"""Unit + integration tests for integrator.py (serves M5, TASKS.md Task 5).

Covers the pure/unit-level helpers (``load_records``, ``_split_top_level_objects``,
``build_summary``, ``process_transaction``) in isolation, plus one full end-to-end
``run_pipeline`` test driven against the real ``sample-transactions.json`` and a second
``run_pipeline`` test driven against a synthetic sample file containing a malformed record, to
prove the batch is never aborted. The filesystem is isolated per test via PIPELINE_SHARED_ROOT /
PIPELINE_LOGS_DIR env vars pointing at pytest's tmp_path, so no test ever touches the project's
real shared/ or logs/ tree.
"""

from __future__ import annotations

import copy
import json
import sys as _sys
from pathlib import Path

import pytest

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import protocol
import integrator

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


def _write_result(transaction_id: str, data_overrides: dict) -> None:
    message = protocol.build_message(
        {"transaction_id": transaction_id, **data_overrides},
        source_agent="test",
        target_agent="integrator",
        message_type="result",
    )
    protocol.write_result(message)


# ---------------------------------------------------------------------------
# _split_top_level_objects
# ---------------------------------------------------------------------------


def test_split_top_level_objects_handles_quoted_braces():
    text = '[{"a": "value with { brace"}, {"b": 2}]'

    chunks = integrator._split_top_level_objects(text)

    assert len(chunks) == 2
    assert json.loads(chunks[0])["a"] == "value with { brace"
    assert json.loads(chunks[1])["b"] == 2


def test_split_top_level_objects_ignores_text_outside_braces():
    text = 'prefix noise [ {"x": 1} , garbage , {"y": 2} ] suffix'

    chunks = integrator._split_top_level_objects(text)

    assert [json.loads(c) for c in chunks] == [{"x": 1}, {"y": 2}]


# ---------------------------------------------------------------------------
# load_records: well-formed, single-dict-wrapped, and malformed-recovery paths
# ---------------------------------------------------------------------------


def test_load_records_well_formed_sample_file():
    records, malformed = integrator.load_records(SAMPLE_PATH)

    assert malformed == 0
    assert len(records) == 8
    assert {r["transaction_id"] for r in records} == {f"TXN00{i}" for i in range(1, 9)}


def test_load_records_single_dict_wrapped(tmp_path):
    record = _sample("TXN001")
    path = tmp_path / "single-record.json"
    path.write_text(json.dumps(record), encoding="utf-8")

    records, malformed = integrator.load_records(path)

    assert malformed == 0
    assert records == [record]


def test_load_records_strict_parse_skips_non_dict_and_id_less_entries(tmp_path):
    path = tmp_path / "mixed.json"
    path.write_text(
        json.dumps([_sample("TXN001"), "not-a-dict", {"amount": "1.00"}]),
        encoding="utf-8",
    )

    records, malformed = integrator.load_records(path)

    assert malformed == 2  # the bare string, and the dict with no transaction_id
    assert len(records) == 1
    assert records[0]["transaction_id"] == "TXN001"


def test_load_records_tolerant_recovery_on_malformed_top_level_json(tmp_path):
    valid1 = _sample("TXN001")
    valid2 = _sample("TXN002")
    # Deliberately malformed overall array (bad object between two valid ones, and a missing
    # comma) so strict json.loads fails and the tolerant per-object recovery path is exercised.
    text = (
        "["
        + json.dumps(valid1)
        + ","
        + '{"transaction_id": "BAD1", "amount": ,}'
        + ","
        + json.dumps(valid2)
        + "]"
    )
    path = tmp_path / "malformed.json"
    path.write_text(text, encoding="utf-8")

    records, malformed = integrator.load_records(path)

    assert malformed == 1
    assert {r["transaction_id"] for r in records} == {"TXN001", "TXN002"}


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------


def test_build_summary_aggregates_all_result_kinds():
    _write_result(
        "R-CLEARED",
        {"status": "cleared", "decision": "cleared", "reason": [], "requires_report": False},
    )
    _write_result(
        "R-FLAGGED",
        {
            "status": "flagged",
            "decision": "flagged",
            "reason": ["regulatory_reporting_threshold"],
            "requires_report": True,
        },
    )
    _write_result(
        "R-REJECTED-COMPLIANCE",
        {
            "status": "rejected",
            "decision": "rejected",
            "reason": ["blocked_account"],
            "requires_report": False,
        },
    )
    _write_result(
        "R-REJECTED-VALIDATION",
        {"status": "rejected", "reason": "invalid_currency_code:XYZ"},
    )
    _write_result(
        "R-ERROR",
        {"status": "error", "decision": "error", "reason": ["pipeline_error"]},
    )

    summary = integrator.build_summary(malformed_count=3)

    assert summary["total"] == 5
    assert summary["validated"] == 3  # cleared + flagged + rejected_at_compliance
    assert summary["cleared"] == 1
    assert summary["flagged"] == 1
    assert summary["rejected_at_compliance"] == 1
    assert summary["rejected_at_validation"] == 1
    assert summary["requires_report"] == 1
    assert summary["error_count"] == 1
    assert summary["malformed_input_count"] == 3
    assert isinstance(summary["generated_at"], str) and summary["generated_at"]


def test_build_summary_ignores_the_summary_file_itself_and_malformed_result_files():
    _write_result(
        "R-CLEARED",
        {"status": "cleared", "decision": "cleared", "reason": [], "requires_report": False},
    )
    # A pre-existing summary.json in results/ must not be double-counted as a transaction result.
    (protocol.shared_subdir("results") / "summary.json").write_text(
        json.dumps({"total": 999}), encoding="utf-8"
    )
    # A malformed result file must be skipped rather than crashing the aggregation.
    (protocol.shared_subdir("results") / "CORRUPT.json").write_text(
        "{not valid json", encoding="utf-8"
    )

    summary = integrator.build_summary(malformed_count=0)

    assert summary["total"] == 1
    assert summary["cleared"] == 1


def test_build_summary_empty_results_directory():
    summary = integrator.build_summary(malformed_count=0)

    assert summary["total"] == 0
    assert summary["malformed_input_count"] == 0


# ---------------------------------------------------------------------------
# process_transaction: single-message drive through validator -> fraud -> compliance
# ---------------------------------------------------------------------------


def test_process_transaction_full_success_path_reaches_compliance_decision():
    message = protocol.build_message(
        _sample("TXN001"),
        source_agent="integrator",
        target_agent="transaction_validator",
    )

    result = integrator.process_transaction(message)

    assert result["data"]["decision"] in {"cleared", "flagged", "rejected"}
    assert protocol.result_exists("TXN001")


def test_process_transaction_validator_rejection_short_circuits_before_compliance():
    message = protocol.build_message(
        _sample("TXN006"),  # invalid ISO 4217 currency
        source_agent="integrator",
        target_agent="transaction_validator",
    )

    result = integrator.process_transaction(message)

    assert result["data"]["status"] == "rejected"
    assert "decision" not in result["data"]
    assert protocol.result_exists("TXN006")


def test_process_transaction_default_order_is_stamped_on_the_result():
    message = protocol.build_message(
        _sample("TXN001"),
        source_agent="integrator",
        target_agent="transaction_validator",
    )

    result = integrator.process_transaction(message)

    assert result["data"]["pipeline_order_used"] == [
        "transaction_validator",
        "fraud_detector",
        "compliance_checker",
    ]


def test_process_transaction_honours_a_custom_pipeline_order():
    data = _sample("TXN001")
    data["pipeline_order"] = ["transaction_validator", "compliance_checker", "fraud_detector"]
    message = protocol.build_message(
        data, source_agent="integrator", target_agent="transaction_validator"
    )

    result = integrator.process_transaction(message)

    assert result["data"]["pipeline_order_used"] == [
        "transaction_validator",
        "compliance_checker",
        "fraud_detector",
    ]
    assert result["data"]["decision"] in {"cleared", "flagged", "rejected"}
    assert protocol.result_exists("TXN001")


def test_process_transaction_falls_back_to_default_on_invalid_pipeline_order():
    data = _sample("TXN001")
    data["pipeline_order"] = ["fraud_detector", "compliance_checker"]  # missing validator
    message = protocol.build_message(
        data, source_agent="integrator", target_agent="transaction_validator"
    )

    result = integrator.process_transaction(message)

    assert result["data"]["pipeline_order_used"] == [
        "transaction_validator",
        "fraud_detector",
        "compliance_checker",
    ]
    assert protocol.result_exists("TXN001")


def test_process_transaction_is_idempotent_on_existing_result():
    data = _sample("TXN001")
    message = protocol.build_message(
        data, source_agent="integrator", target_agent="transaction_validator"
    )

    first = integrator.process_transaction(message)

    second_message = protocol.build_message(
        copy.deepcopy(data), source_agent="integrator", target_agent="transaction_validator"
    )
    second = integrator.process_transaction(second_message)

    assert second == first
    result_files = list(protocol.shared_subdir("results").glob("TXN001*"))
    assert len(result_files) == 1


# ---------------------------------------------------------------------------
# run_pipeline: full end-to-end orchestration against an isolated shared_root
# ---------------------------------------------------------------------------


def test_run_pipeline_end_to_end_over_sample_transactions(tmp_path):
    shared_root = tmp_path / "shared"

    summary = integrator.run_pipeline(
        str(SAMPLE_PATH), shared_root=shared_root, timeout=5
    )

    sample_ids = {r["transaction_id"] for r in _sample_records()}
    for txn_id in sample_ids:
        assert protocol.result_exists(txn_id), f"missing terminal result for {txn_id}"

    summary_path = protocol.shared_subdir("results") / "summary.json"
    assert summary_path.exists()
    on_disk_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert on_disk_summary["total"] == summary["total"]
    assert summary["total"] == len(sample_ids)
    assert summary["malformed_input_count"] == 0
    assert summary["validated"] == len(sample_ids) - summary["rejected_at_validation"]

    # TXN006 has an invalid currency -> rejected at validation, never reaches compliance.
    txn006_result = protocol.read_result("TXN006")
    assert txn006_result["data"]["status"] == "rejected"
    assert "decision" not in txn006_result["data"]


def test_run_pipeline_is_idempotent_on_rerun(tmp_path):
    shared_root = tmp_path / "shared"

    integrator.run_pipeline(str(SAMPLE_PATH), shared_root=shared_root, timeout=5)
    first_count = len(list(protocol.shared_subdir("results").glob("TXN*.json")))

    second_summary = integrator.run_pipeline(str(SAMPLE_PATH), shared_root=shared_root, timeout=5)
    second_count = len(list(protocol.shared_subdir("results").glob("TXN*.json")))

    assert second_count == first_count  # no duplicate result files on rerun
    assert second_summary["total"] == first_count


def test_run_pipeline_malformed_record_does_not_abort_the_batch(tmp_path):
    valid1 = _sample("TXN001")
    valid2 = _sample("TXN002")
    text = (
        "["
        + json.dumps(valid1)
        + ","
        + '{"transaction_id": "BAD1", "amount": ,}'
        + ","
        + json.dumps(valid2)
        + "]"
    )
    sample_file = tmp_path / "custom-sample.json"
    sample_file.write_text(text, encoding="utf-8")
    shared_root = tmp_path / "shared"

    summary = integrator.run_pipeline(str(sample_file), shared_root=shared_root, timeout=5)

    assert summary["malformed_input_count"] == 1
    assert protocol.result_exists("TXN001")
    assert protocol.result_exists("TXN002")
    assert protocol.result_exists("MALFORMED-1")
    malformed_result = protocol.read_result("MALFORMED-1")
    assert malformed_result["data"]["decision"] == "rejected"
    assert malformed_result["data"]["reason"] == ["malformed_input"]
    # The batch was not aborted: both well-formed records still reached a terminal decision.
    assert summary["total"] == 3


def test_run_pipeline_holds_transaction_for_review_on_unexpected_agent_error(
    tmp_path, monkeypatch
):
    """A pipeline-level exception for one transaction must not abort the rest of the batch, and
    must fail closed to an 'error' terminal result rather than being silently dropped."""
    shared_root = tmp_path / "shared"

    original_process_transaction = integrator.process_transaction

    def _flaky_process_transaction(message):
        txn_id = protocol.transaction_id_of(message)
        if txn_id == "TXN002":
            raise RuntimeError("simulated unexpected agent failure")
        return original_process_transaction(message)

    monkeypatch.setattr(integrator, "process_transaction", _flaky_process_transaction)

    summary = integrator.run_pipeline(str(SAMPLE_PATH), shared_root=shared_root, timeout=5)

    txn002_result = protocol.read_result("TXN002")
    assert txn002_result["data"]["status"] == "error"
    assert txn002_result["data"]["decision"] == "error"
    # The rest of the batch still reached a terminal result despite TXN002's failure.
    assert protocol.result_exists("TXN001")
    assert protocol.result_exists("TXN003")
    assert summary["error_count"] == 1
