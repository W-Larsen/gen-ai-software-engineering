"""Unit tests for agents/fraud_detector.py (serves M2).

Table-driven over TXN001-TXN005, TXN007, TXN008 fixtures from sample-transactions.json, asserting
the *exact* risk_score and fraud_review per the documented scoring rules. Each fixture is scored
twice (once via the pure `score_transaction` function, once via the full `process_message` I/O
wrapper for a subset) to prove determinism: identical input -> identical output. The filesystem is
isolated per test via PIPELINE_SHARED_ROOT / PIPELINE_LOGS_DIR env vars pointing at pytest's
tmp_path, so no test ever touches the project's real shared/ or logs/ tree.
"""

from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path

import pytest

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import protocol
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
            data = copy.deepcopy(record)
            data["status"] = "validated"  # as handed off by the transaction validator
            return data
    raise KeyError(transaction_id)


def _incoming_message(data: dict) -> dict:
    return protocol.build_message(
        data, source_agent="transaction_validator", target_agent="fraud_detector"
    )


# ---------------------------------------------------------------------------
# Table-driven expected scores (per specification.md M2 + the acceptance criteria)
# ---------------------------------------------------------------------------

EXPECTED = {
    # txn_id: (risk_score, fraud_review, signals)
    "TXN001": (0, False, []),                                    # 1500 USD, US, 09:00Z
    "TXN002": (50, True, ["high_value"]),                        # 25000 USD, US, 09:15Z
    "TXN003": (0, False, []),                                    # 9999.99 USD boundary, US, 09:30Z
    "TXN004": (35, False, ["off_hours", "cross_border"]),        # 500 EUR, DE, 02:47Z
    "TXN005": (50, True, ["high_value"]),                        # 75000 USD, US, 10:00Z
    "TXN007": (15, False, ["cross_border"]),                     # 100.00 GBP refund, GB, 10:10Z
    "TXN008": (0, False, []),                                    # 3200 USD, US, 10:15Z
}


@pytest.mark.parametrize("txn_id", sorted(EXPECTED))
def test_score_transaction_exact_score_and_determinism(txn_id):
    """Pure scoring function: exact risk_score/fraud_review/signals, scored twice for determinism."""
    data = _sample(txn_id)
    expected_score, expected_review, expected_signals = EXPECTED[txn_id]

    first = fraud_detector.score_transaction(data, fraud_detector.RULES)
    second = fraud_detector.score_transaction(data, fraud_detector.RULES)

    assert first == second  # determinism: identical input -> identical output
    assert first["risk_score"] == expected_score
    assert first["fraud_review"] is expected_review
    assert first["signals"] == expected_signals


@pytest.mark.parametrize("txn_id", sorted(EXPECTED))
def test_process_message_exact_score_and_determinism(txn_id):
    """End-to-end process_message: exact risk_score/fraud_review, re-run twice for determinism."""
    expected_score, expected_review, expected_signals = EXPECTED[txn_id]

    first = fraud_detector.process_message(_incoming_message(_sample(txn_id)))
    assert first["data"]["risk_score"] == expected_score
    assert first["data"]["fraud_review"] is expected_review
    assert first["data"]["fraud_signals"] == expected_signals
    assert first["data"]["status"] == "scored"
    assert first["target_agent"] == "compliance_checker"

    # Re-running process_message on an identical (fresh) input message must yield an identical
    # score (idempotency short-circuits after the first call wrote no shared/results/ entry, so
    # this exercises the pure recompute path, not the duplicate_ignored path).
    second = fraud_detector.process_message(_incoming_message(_sample(txn_id)))
    assert second["data"]["risk_score"] == first["data"]["risk_score"]
    assert second["data"]["fraud_review"] == first["data"]["fraud_review"]
    assert second["data"]["fraud_signals"] == first["data"]["fraud_signals"]


# ---------------------------------------------------------------------------
# Specific acceptance-criteria call-outs (belt-and-suspenders on top of the table above)
# ---------------------------------------------------------------------------


def test_txn002_and_txn005_high_value_flagged_for_review():
    for txn_id in ("TXN002", "TXN005"):
        result = fraud_detector.process_message(_incoming_message(_sample(txn_id)))
        assert result["data"]["risk_score"] >= 50
        assert result["data"]["fraud_review"] is True


def test_txn003_boundary_amount_scores_zero_on_high_value_signal():
    result = fraud_detector.process_message(_incoming_message(_sample("TXN003")))
    assert "high_value" not in result["data"]["fraud_signals"]
    assert result["data"]["risk_score"] == 0
    assert result["data"]["fraud_review"] is False


def test_txn004_off_hours_and_cross_border_signal_but_not_flagged():
    result = fraud_detector.process_message(_incoming_message(_sample("TXN004")))
    assert result["data"]["risk_score"] == 35
    assert set(result["data"]["fraud_signals"]) == {"off_hours", "cross_border"}
    assert result["data"]["fraud_review"] is False


def test_scored_message_is_written_to_output_for_compliance():
    fraud_detector.process_message(_incoming_message(_sample("TXN002")))
    assert (protocol.shared_subdir("output") / "TXN002.json").exists()


# ---------------------------------------------------------------------------
# Idempotency: existing shared/results/ entry short-circuits re-scoring
# ---------------------------------------------------------------------------


def test_duplicate_transaction_with_existing_result_is_idempotent(monkeypatch):
    data = _sample("TXN002")
    message = _incoming_message(data)
    txn_id = protocol.transaction_id_of(message)

    # Simulate a terminal result already produced by a downstream compliance stage.
    terminal = copy.deepcopy(message)
    terminal["data"]["decision"] = "flagged"
    protocol.write_result(terminal)

    write_calls: list[dict] = []
    original_write_message = protocol.write_message

    def _tracked_write_message(msg, subdir, **kwargs):
        write_calls.append(msg)
        return original_write_message(msg, subdir, **kwargs)

    monkeypatch.setattr(protocol, "write_message", _tracked_write_message)

    result = fraud_detector.process_message(message)

    assert result["data"]["decision"] == "flagged"
    assert write_calls == []  # never re-scored/re-written to shared/output/


# ---------------------------------------------------------------------------
# Defensive handling: missing metadata.country must not fabricate a cross-border signal
# ---------------------------------------------------------------------------


def test_missing_country_is_not_treated_as_cross_border():
    data = _sample("TXN001")
    data["metadata"] = {"channel": "online"}  # no country key at all

    outcome = fraud_detector.score_transaction(data, fraud_detector.RULES)

    assert "cross_border" not in outcome["signals"]
    assert outcome["risk_score"] == 0


# ---------------------------------------------------------------------------
# process_message: type/coercion defensiveness
# ---------------------------------------------------------------------------


def test_process_message_non_dict_message_raises_type_error():
    with pytest.raises(TypeError):
        fraud_detector.process_message("not-a-message")


def test_process_message_non_dict_data_is_coerced_before_scoring():
    message = protocol.build_message(
        {}, source_agent="transaction_validator", target_agent="fraud_detector"
    )
    message["data"] = ["not", "a", "dict"]

    # Coercion happens first (message["data"] becomes {}); scoring then fails closed (rather than
    # raising) because the coerced empty dict has neither "amount" nor "timestamp" -- a non-default
    # pipeline order could otherwise route unvalidated data here, so process_message must never
    # crash the batch.
    result = fraud_detector.process_message(message)

    assert isinstance(message["data"], dict)
    assert result["data"]["status"] == "error"
    assert result["data"]["reason"] == ["fraud_scoring_error"]


# ---------------------------------------------------------------------------
# _process_queue: drains shared/output/ for validated messages awaiting scoring
# ---------------------------------------------------------------------------


def test_process_queue_scores_validated_message_and_rewrites_output():
    protocol.write_message(_incoming_message(_sample("TXN001")), "output")

    result = fraud_detector._process_queue()

    assert result["processed"] == 1
    assert list(protocol.shared_subdir("processing").glob("*.json")) == []
    rescored = protocol.read_message(protocol.shared_subdir("output") / "TXN001.json")
    assert rescored["data"]["status"] == "scored"
    assert "risk_score" in rescored["data"]


def test_process_queue_skips_malformed_json_file_without_aborting_batch():
    output_dir = protocol.shared_subdir("output")
    bad_path = output_dir / "BAD001.json"
    bad_path.write_text("{not valid json", encoding="utf-8")

    protocol.write_message(_incoming_message(_sample("TXN001")), "output")

    result = fraud_detector._process_queue()

    assert result["processed"] == 1
    assert not bad_path.exists()


def test_process_queue_leaves_non_validated_message_untouched():
    data = _sample("TXN001")
    data["status"] = "scored"  # already past this agent's stage
    protocol.write_message(_incoming_message(data), "output")

    result = fraud_detector._process_queue()

    assert result["processed"] == 0
    still_there = protocol.read_message(protocol.shared_subdir("output") / "TXN001.json")
    assert still_there["data"]["status"] == "scored"


def test_process_queue_tolerates_unlink_failures_on_cleanup(monkeypatch):
    """Best-effort cleanup unlinks must never crash the batch (edge case: locked/removed file)."""
    output_dir = protocol.shared_subdir("output")
    bad_path = output_dir / "BAD002.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    protocol.write_message(_incoming_message(_sample("TXN001")), "output")

    def _raise_unlink(self, *args, **kwargs):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(Path, "unlink", _raise_unlink)

    result = fraud_detector._process_queue()

    assert result["processed"] == 1


def test_process_queue_skips_on_move_race_condition(monkeypatch):
    """Simulate the file disappearing/mutating between the initial read and the move-to-processing
    step (edge case: a concurrent writer corrupts the file mid-drain)."""
    protocol.write_message(_incoming_message(_sample("TXN001")), "output")

    def _raise(*_args, **_kwargs):
        raise ValueError("malformed_input: simulated race")

    monkeypatch.setattr(protocol, "move_message", _raise)

    result = fraud_detector._process_queue()

    assert result["processed"] == 0


# ---------------------------------------------------------------------------
# main(): CLI entrypoint, and the ``python -m`` / ``__main__`` guard
# ---------------------------------------------------------------------------


def test_main_drains_the_queue(capsys):
    protocol.write_message(_incoming_message(_sample("TXN001")), "output")

    exit_code = fraud_detector.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Scored 1 message(s) from shared/output/." in captured.out


def test_main_handles_empty_queue(capsys):
    exit_code = fraud_detector.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Scored 0 message(s) from shared/output/." in captured.out


def test_module_dunder_main_entrypoint(monkeypatch):
    """Exercise ``if __name__ == '__main__': raise SystemExit(main())`` directly."""
    monkeypatch.setattr(_sys, "argv", ["fraud_detector"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("agents.fraud_detector", run_name="__main__")

    assert exc_info.value.code == 0
